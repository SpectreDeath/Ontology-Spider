"""Machine API: Python functions and JSON-ready interfaces for the engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ontology_spider.engine import Engine, QueryResult
from ontology_spider.export import to_dialog, to_dot, to_html, to_json
from ontology_spider.model import OntologyModel
from ontology_spider.seam import DialogModelSource, JsonModelSource, ModelSource
from ontology_spider.validation import OntologyValidator


def load_model(source: str | Path | ModelSource) -> OntologyModel:
    """Load an OntologyModel from a file path, raw string, or ModelSource adapter."""
    if isinstance(source, ModelSource):
        return source.load()

    if isinstance(source, Path) or (isinstance(source, str) and ("\n" not in source and Path(source).is_file())):
        p = Path(source)
        if p.suffix.lower() == ".json":
            return JsonModelSource(p).load()
        elif p.suffix.lower() == ".dialog":
            return DialogModelSource(p).load()
        else:
            raise ValueError(f"Unrecognized file extension: {p.suffix}")

    # String source: check if JSON or dialog
    s = str(source).strip()
    if s.startswith("{"):
        return JsonModelSource(s).load()
    return DialogModelSource(s).load()


def run_query(model: OntologyModel, query_str: str) -> QueryResult:
    """Execute a query against a model, returning answers, explanations, and provenance."""
    engine = Engine()
    return engine.query(model, query_str)


def validate_model(model: OntologyModel) -> list[dict[str, Any]]:
    """Validate a model and return violations with offending assertion IDs."""
    validator = OntologyValidator()
    violations = validator.validate(model)
    return [
        {
            "check_type": v.check_type,
            "message": v.message,
            "offending_assertion_ids": v.offending_assertion_ids,
            "details": v.details,
        }
        for v in violations
    ]


def export_model(model: OntologyModel, format: str = "json") -> str:
    """Export model to 'json', 'dialog', 'dot', or 'html'."""
    fmt = format.lower().strip()
    if fmt == "json":
        return to_json(model)
    elif fmt == "dialog":
        return to_dialog(model)
    elif fmt == "dot":
        return to_dot(model)
    elif fmt == "html":
        return to_html(model)
    else:
        raise ValueError(f"Unsupported export format '{format}'. Allowed: json, dialog, dot, html.")
