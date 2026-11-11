"""ModelSource interface and built-in model readers (JSON and .dialog)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from ontology_spider.dialog import (
    DialogAssertion,
    DialogEntityDecl,
    DialogImport,
    parse_dialog,
)
from ontology_spider.model import (
    OntologyModel,
    Provenance,
    Relation,
)


class ImportCycleError(Exception):
    """Raised when an import cycle is detected."""


def load_imported_model(
    import_path: str | Path,
    base_dir: Path | None = None,
    import_chain: tuple[Path, ...] = (),
) -> OntologyModel:
    """Resolve and load an imported model (.json or .dialog) with cycle detection."""
    target_path = Path(import_path)
    if not target_path.is_absolute():
        resolved_base = base_dir or Path.cwd()
        target_path = (resolved_base / target_path).resolve()
    else:
        target_path = target_path.resolve()

    if target_path in import_chain:
        chain_strs = [str(p) for p in import_chain] + [str(target_path)]
        raise ImportCycleError(f"Cyclic import detected: {' -> '.join(chain_strs)}")

    new_chain = import_chain + (target_path,)

    if target_path.suffix.lower() == ".json":
        return JsonModelSource(target_path).load()
    elif target_path.suffix.lower() == ".dialog":
        return DialogModelSource(target_path, base_dir=target_path.parent, import_chain=new_chain).load()
    else:
        raise ValueError(f"Unsupported model import format: {target_path}")


class ModelSource(ABC):
    """Clean pluggable seam interface for loading ontology models."""

    @abstractmethod
    def load(self) -> OntologyModel:
        """Load and return an OntologyModel instance."""
        raise NotImplementedError


class JsonModelSource(ModelSource):
    """Loads an ontology from a JSON graph file or raw JSON string."""

    def __init__(self, source: str | Path) -> None:
        self.source = source

    def load(self) -> OntologyModel:
        if isinstance(self.source, Path) or (
            isinstance(self.source, str) and not self.source.strip().startswith("{")
        ):
            path = Path(self.source)
            if not path.is_file():
                raise FileNotFoundError(f"JSON model file not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(self.source)

        return OntologyModel.from_dict(data)


class DialogModelSource(ModelSource):
    """Loads an ontology directly from a .dialog authoring file or script.

    Dogfoods the Dialog language as an authoring format for Track 1b.
    """

    def __init__(
        self,
        source: str | Path,
        base_dir: str | Path | None = None,
        import_chain: tuple[Path, ...] = (),
    ) -> None:
        self.source = source
        self.import_chain = import_chain
        if isinstance(source, Path):
            self.base_dir = source.parent
        elif base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path.cwd()

    def load(self) -> OntologyModel:
        if isinstance(self.source, Path) or (
            isinstance(self.source, str)
            and ("\n" not in self.source and Path(self.source).is_file())
        ):
            path = Path(self.source).resolve()
            text = path.read_text(encoding="utf-8")
            source_label = str(path)
            current_chain = self.import_chain or (path,)
        else:
            text = str(self.source)
            source_label = "inline.dialog"
            current_chain = self.import_chain

        doc = parse_dialog(text)
        model = OntologyModel(uri=doc.uri)

        # Handle imports first
        for stmt in doc.statements:
            if isinstance(stmt, DialogImport):
                sub_model = load_imported_model(
                    stmt.path,
                    base_dir=self.base_dir,
                    import_chain=current_chain,
                )

                # Merge entities and assertions
                for entity in sub_model.entities.values():
                    model.add_entity(entity)
                for asrt in sub_model.assertions.values():
                    model.add_assertion(
                        relation=asrt.relation,
                        provenance=asrt.provenance,
                        assertion_id=asrt.assertion_id,
                        attributes=asrt.attributes,
                    )

        # Process entities and assertions
        for idx, stmt in enumerate(doc.statements, start=1):
            if isinstance(stmt, DialogEntityDecl):
                ent_attrs = dict(stmt.attributes)
                name = ent_attrs.pop("name", None)
                model.upsert_entity(stmt.entity_id, name=name, attributes=ent_attrs)
            elif isinstance(stmt, DialogAssertion):
                attrs = dict(stmt.attributes)
                aid = attrs.pop("_id", None)
                src = attrs.pop("_source", source_label)
                tid = attrs.pop("_turn", f"stmt_{idx}")
                ts = attrs.pop("_timestamp", None)
                parents_str = attrs.pop("_parents", None)
                parents = [p.strip() for p in str(parents_str).split(",") if p.strip()] if parents_str else []
                kwargs: dict[str, Any] = {"source": src, "turn_id": tid}
                if ts:
                    kwargs["timestamp"] = str(ts)
                if parents:
                    kwargs["parent_turn_ids"] = parents
                prov = Provenance(**kwargs)
                model.add_assertion(
                    relation=Relation(
                        subject=stmt.subject,
                        predicate=stmt.predicate,
                        object=stmt.object,
                    ),
                    provenance=prov,
                    assertion_id=aid,
                    attributes=attrs,
                )

        return model
