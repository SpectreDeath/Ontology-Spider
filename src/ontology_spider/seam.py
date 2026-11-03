"""ModelSource interface and built-in model readers (JSON and .dialog)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from ontology_spider.dialog import DialogAssertion, DialogImport, parse_dialog
from ontology_spider.model import (
    Entity,
    OntologyModel,
    Provenance,
    Relation,
)


class ModelSource(ABC):
    """Clean pluggable seam interface for loading ontology models."""

    @abstractmethod
    def load(self) -> OntologyModel:
        """Load and return an OntologyModel instance."""
        raise NotImplementedError


class JsonModelSource(ModelSource):
    """Loads an ontology from a JSON graph file or raw JSON string."""

    def __init__(self, source: Union[str, Path]) -> None:
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

    def __init__(self, source: Union[str, Path], base_dir: Union[str, Path, None] = None) -> None:
        self.source = source
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
            path = Path(self.source)
            text = path.read_text(encoding="utf-8")
            source_label = str(path)
        else:
            text = str(self.source)
            source_label = "inline.dialog"

        doc = parse_dialog(text)
        model = OntologyModel(uri=doc.uri)

        # Handle imports first
        for stmt in doc.statements:
            if isinstance(stmt, DialogImport):
                import_path = Path(stmt.path)
                if not import_path.is_absolute():
                    import_path = self.base_dir / import_path
                if import_path.suffix.lower() == ".json":
                    sub_model = JsonModelSource(import_path).load()
                elif import_path.suffix.lower() == ".dialog":
                    sub_model = DialogModelSource(import_path).load()
                else:
                    raise ValueError(f"Unsupported model import format: {import_path}")

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

        # Process assertions
        for idx, stmt in enumerate(doc.statements, start=1):
            if isinstance(stmt, DialogAssertion):
                prov = Provenance(
                    source=source_label,
                    turn_id=f"stmt_{idx}",
                )
                model.add_assertion(
                    relation=Relation(
                        subject=stmt.subject,
                        predicate=stmt.predicate,
                        object=stmt.object,
                    ),
                    provenance=prov,
                    attributes=stmt.attributes,
                )

        return model
