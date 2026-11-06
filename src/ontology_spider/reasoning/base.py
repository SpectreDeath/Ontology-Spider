"""Base protocols, specs, and result structures for reasoner backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from ontology_spider.model import Assertion, OntologyModel


@dataclass
class Explanation:
    """Audit trace proving how an answer was derived."""
    rules_fired: list[str] = field(default_factory=list)
    fact_ids: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    provenance_assertions: list[Assertion] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        if self.rules_fired:
            lines.append(f"Rules: {', '.join(self.rules_fired)}")
        if self.path:
            lines.append(f"Path: {' -> '.join(self.path)}")
        if self.provenance_assertions:
            lines.append("Base Facts:")
            for asrt in self.provenance_assertions:
                p = asrt.provenance
                src_info = f"source={p.source}"
                if p.turn_id:
                    src_info += f", turn={p.turn_id}"
                lines.append(
                    f"  - [{asrt.assertion_id}] ({asrt.relation.subject} {asrt.relation.predicate} {asrt.relation.object}) ({src_info})"
                )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_fired": list(self.rules_fired),
            "fact_ids": list(self.fact_ids),
            "path": list(self.path),
            "provenance_assertions": [a.to_dict() for a in self.provenance_assertions],
        }


@dataclass
class ReasonerAnswer:
    """An individual derived answer item with its explanation."""
    value: Any
    explanation: Explanation

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "rules_fired": self.explanation.rules_fired,
            "fact_ids": self.explanation.fact_ids,
            "path": self.explanation.path,
            "provenance": [a.to_dict() for a in self.explanation.provenance_assertions],
        }


@dataclass
class ReasonerResult:
    """Complete results of a query evaluation."""
    query_goal: str
    answers: list[ReasonerAnswer]
    raw_response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_goal": self.query_goal,
            "answers": [a.to_dict() for a in self.answers],
            "raw_response": self.raw_response,
        }


@dataclass(frozen=True)
class QuerySpec:
    """Standardized representation of a query passed to any reasoner backend."""
    kind: str  # "lookup", "ancestors", "transitive", "recommend", "filter", "pattern"
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    filter_key: Optional[str] = None
    filter_val: Optional[Any] = None
    filter_attributes: Mapping[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 10
    max_inferences: int = 1_000_000


@runtime_checkable
class Reasoner(Protocol):
    """Protocol for reasoners (Prolog, Python, hybrid)."""

    @property
    def is_available(self) -> bool:
        ...

    @property
    def name(self) -> str:
        ...

    def query(self, model: OntologyModel, spec: QuerySpec) -> ReasonerResult:
        ...
