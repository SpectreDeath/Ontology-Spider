"""Export base reasoning classes."""

from ontology_spider.reasoning.base import (
    Explanation,
    QuerySpec,
    Reasoner,
    ReasonerAnswer,
    ReasonerResult,
)
from ontology_spider.reasoning.python_backend import PythonReasoner

__all__ = [
    "Explanation",
    "PythonReasoner",
    "QuerySpec",
    "Reasoner",
    "ReasonerAnswer",
    "ReasonerResult",
]
