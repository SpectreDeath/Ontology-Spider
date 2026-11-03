"""ModelSource interface and built-in model readers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from ontology_spider.model import OntologyModel


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
