"""Standalone adapter demonstrating how a vault export loads through the Track 1 ModelSource seam.

Imports zero brain-harness code. Proves that the future plugin will be a clean, thin adapter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from ontology_spider.model import (
    Entity,
    OntologyModel,
    Provenance,
    Relation,
)
from ontology_spider.seam import ModelSource


class VaultModelSource(ModelSource):
    """Adapter loading vault-shaped items and typed edges into an OntologyModel."""

    def __init__(self, source: Union[str, Path, dict[str, Any]]) -> None:
        if isinstance(source, dict):
            self.data = source
            self.source_label = "memory_dict"
        elif isinstance(source, Path) or (isinstance(source, str) and not source.strip().startswith("{")):
            p = Path(source)
            self.data = json.loads(p.read_text(encoding="utf-8"))
            self.source_label = str(p)
        else:
            self.data = json.loads(source)
            self.source_label = "json_string"

    def load(self) -> OntologyModel:
        vault_id = self.data.get("vault_id", "unnamed_vault")
        model = OntologyModel(uri=f"urn:vault:{vault_id}")

        # Map Items -> Entities
        for item in self.data.get("items", []):
            item_id = item["id"]
            meta = dict(item.get("metadata", {}))
            title = meta.get("title", item_id)
            entity = Entity(id=item_id, name=title, attributes=meta)
            model.add_entity(entity)

            # If item specifies a type, also record it as an instance_of assertion
            item_type = item.get("type")
            if item_type:
                prov = Provenance(source=self.source_label, turn_id="vault_item_type")
                model.add_assertion(
                    relation=Relation(subject=item_id, predicate="instance_of", object=item_type),
                    provenance=prov,
                )

        # Map Edges -> Relations
        for edge in self.data.get("edges", []):
            prov = Provenance(source=self.source_label, turn_id="vault_edge")
            model.add_assertion(
                relation=Relation(
                    subject=edge["from"],
                    predicate=edge["rel"],
                    object=edge["to"],
                ),
                provenance=prov,
                attributes=dict(edge.get("metadata", {})),
            )

        return model
