"""Unified QueryResult, Session, and SessionManager for CLI, Machine API, and MCP."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Union

from ontology_spider.dialog import (
    DialogAssertion,
    DialogDoc,
    DialogEntityDecl,
    DialogImport,
    DialogQuery,
    parse_dialog,
)
from ontology_spider.model import (
    Assertion,
    Entity,
    OntologyModel,
    Provenance,
    Relation,
)
from ontology_spider.prolog.reasoner import PrologReasoner
from ontology_spider.reasoning.base import (
    Explanation,
    QuerySpec,
    Reasoner,
    ReasonerAnswer,
    ReasonerResult,
)
from ontology_spider.reasoning.python_backend import PythonReasoner
from ontology_spider.seam import load_imported_model
from ontology_spider.traversal import TraversalDialogueManager


@dataclass
class QueryResult:
    """Unified, JSON-serializable query result supporting attribute and dict access."""
    query_text: str
    statement_type: str  # "query", "explain", "assertion", "entity", "import"
    summary: str
    answers: list[dict[str, Any]] = field(default_factory=list)
    raw_answers: list[ReasonerAnswer] = field(default_factory=list)
    explanation: Optional[Explanation] = None

    def __getitem__(self, key: str) -> Any:
        if key == "query":
            return self.query_text
        elif key == "statement_type":
            return self.statement_type
        elif key == "summary":
            return self.summary
        elif key == "answers":
            return self.answers
        elif key == "explanation":
            return self.explanation
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query_text,
            "statement_type": self.statement_type,
            "summary": self.summary,
            "answers": self.answers,
            "explanation": self.explanation.to_dict() if self.explanation else None,
        }


class Session:
    """An interactive or programmatic ontology engine session."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        model: Optional[OntologyModel] = None,
        reasoner: Optional[Reasoner] = None,
        base_dir: Optional[Path] = None,
        timeout_seconds: float = 10.0,
        max_inferences: int = 1_000_000,
    ) -> None:
        self.session_id: str = session_id or uuid.uuid4().hex[:8]
        self.model: OntologyModel = model or OntologyModel(uri=f"urn:dialog:session:{self.session_id}")
        self.base_dir: Path = base_dir or Path.cwd()
        self.timeout_seconds: float = timeout_seconds
        self.max_inferences: int = max_inferences

        if reasoner is not None:
            self.reasoner = reasoner
        else:
            prolog = PrologReasoner()
            self.reasoner = prolog if prolog.is_available else PythonReasoner()

        self.python_reasoner = PythonReasoner()
        self.traversal = TraversalDialogueManager(
            model=self.model,
            reasoner=self.reasoner,
            timeout_seconds=self.timeout_seconds,
            max_inferences=self.max_inferences,
        )
        self.turn_counter: int = 0
        self.history: list[QueryResult] = []
        self.last_query_result: Optional[QueryResult] = None

    def execute(self, text: str) -> list[QueryResult]:
        """Execute one or more .dialog statements."""
        clean = text.strip()
        if not clean:
            return []

        doc = parse_dialog(f"dialog {self.model.uri}\n{clean}")
        results: list[QueryResult] = []
        for stmt in doc.statements:
            res = self.execute_statement(stmt)
            results.append(res)
            self.history.append(res)
        return results

    def execute_statement(
        self,
        stmt: Union[DialogImport, DialogEntityDecl, DialogAssertion, DialogQuery],
    ) -> QueryResult:
        self.turn_counter += 1
        turn_id = f"turn_{self.turn_counter}"

        if isinstance(stmt, DialogImport):
            sub_model = load_imported_model(stmt.path, base_dir=self.base_dir)
            for ent in sub_model.entities.values():
                self.model.add_entity(ent)
            for asrt in sub_model.assertions.values():
                self.model.add_assertion(
                    relation=asrt.relation,
                    provenance=asrt.provenance,
                    assertion_id=asrt.assertion_id,
                    attributes=asrt.attributes,
                )
            summary = f"Imported model from {Path(stmt.path).name} ({len(sub_model.assertions)} assertions)"
            return QueryResult(
                query_text=f"import {stmt.path}",
                statement_type="import",
                summary=summary,
            )

        if isinstance(stmt, DialogEntityDecl):
            ent_attrs = dict(stmt.attributes)
            name = ent_attrs.pop("name", None)
            self.model.upsert_entity(stmt.entity_id, name=name, attributes=ent_attrs)
            summary = f"Declared entity: {stmt.entity_id} with {len(stmt.attributes)} attributes"
            return QueryResult(
                query_text=f"entity {stmt.entity_id}",
                statement_type="entity",
                summary=summary,
            )

        if isinstance(stmt, DialogAssertion):
            attrs = dict(stmt.attributes)
            aid = attrs.pop("_id", None)
            src = attrs.pop("_source", f"session:{self.session_id}")
            tid = attrs.pop("_turn", turn_id)
            ts = attrs.pop("_timestamp", None)
            parents_str = attrs.pop("_parents", None)
            parents = [p.strip() for p in str(parents_str).split(",") if p.strip()] if parents_str else []
            kwargs: dict[str, Any] = {"source": src, "turn_id": tid}
            if ts:
                kwargs["timestamp"] = str(ts)
            if parents:
                kwargs["parent_turn_ids"] = parents
            prov = Provenance(**kwargs)
            asrt = self.model.add_assertion(
                relation=Relation(stmt.subject, stmt.predicate, stmt.object),
                provenance=prov,
                assertion_id=aid,
                attributes=attrs,
            )
            summary = f"Asserted: ({stmt.subject} {stmt.predicate} {stmt.object}) [{asrt.assertion_id}]"
            return QueryResult(
                query_text=f"assert {stmt.subject} {stmt.predicate} {stmt.object}",
                statement_type="assertion",
                summary=summary,
            )

        if isinstance(stmt, DialogQuery):
            return self._execute_query(stmt)

        raise ValueError(f"Unknown statement: {stmt}")

    def assert_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        source: str = "engine",
        **attributes: Any,
    ) -> Assertion:
        prov = Provenance(source=source)
        return self.model.add_assertion(Relation(subject, predicate, object), prov, **attributes)

    def declare_entity(self, entity_id: str, **attributes: Any) -> Any:
        return self.model.upsert_entity(entity_id, **attributes)

    def retract_assertion(self, assertion_id: str) -> bool:
        return self.model.retract_assertion(assertion_id)

    def run_dialog(self, dialog_text: str) -> QueryResult:
        results = self.execute(dialog_text)
        if results:
            return results[-1]
        return QueryResult(query_text=dialog_text, statement_type="batch", summary="Empty dialog executed.")

    def _execute_query(self, query: DialogQuery) -> QueryResult:
        if query.kind == "explain":
            if query.subquery is not None:
                self._execute_query(query.subquery)

            if not self.last_query_result or not self.last_query_result.raw_answers:
                return QueryResult(
                    query_text=query.raw_text or "explain",
                    statement_type="explain",
                    summary="No preceding query answer to explain.",
                )

            lines = ["Explanation for previous answers:"]
            for idx, ans in enumerate(self.last_query_result.raw_answers, start=1):
                lines.append(f"Answer #{idx} [{ans.value}]:")
                exp_summary = ans.explanation.summary()
                for exp_line in exp_summary.splitlines():
                    lines.append(f"  {exp_line}")

            first_explanation = self.last_query_result.raw_answers[0].explanation
            return QueryResult(
                query_text=query.raw_text or "explain",
                statement_type="explain",
                summary="\n".join(lines),
                answers=self.last_query_result.answers,
                raw_answers=self.last_query_result.raw_answers,
                explanation=first_explanation,
            )

        # Standard queries
        spec = QuerySpec(
            kind=query.kind,
            subject=query.subject,
            predicate=query.predicate,
            object=query.object,
            filter_key=query.filter_key,
            filter_val=query.filter_val,
            filter_attributes=query.filter_attributes,
            timeout_seconds=float(self.timeout_seconds),
            max_inferences=int(self.max_inferences),
        )

        res = self.reasoner.query(self.model, spec)
        formatted_answers = [
            {
                "value": a.value,
                "rules_fired": a.explanation.rules_fired,
                "path": a.explanation.path,
                "fact_ids": a.explanation.fact_ids,
                "provenance": [asrt.to_dict() for asrt in a.explanation.provenance_assertions],
            }
            for a in res.answers
        ]

        summary_vals = [str(a.value) for a in res.answers]
        summary = f"Query {query.kind}: {', '.join(summary_vals) if summary_vals else 'none'}"

        q_res = QueryResult(
            query_text=query.raw_text or f"query {query.kind}",
            statement_type="query",
            summary=summary,
            answers=formatted_answers,
            raw_answers=res.answers,
            explanation=res.answers[0].explanation if res.answers else None,
        )
        self.last_query_result = q_res
        return q_res


class SessionManager:
    """Manages active ontology sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create_session(
        self,
        session_id: Optional[str] = None,
        model: Optional[OntologyModel] = None,
        reasoner: Optional[Reasoner] = None,
        timeout_seconds: float = 10.0,
        max_inferences: int = 1_000_000,
        **kwargs: Any,
    ) -> Session:
        sid = session_id or uuid.uuid4().hex[:8]
        session = Session(
            session_id=sid,
            model=model,
            reasoner=reasoner,
            timeout_seconds=timeout_seconds,
            max_inferences=max_inferences,
            **kwargs,
        )
        self._sessions[sid] = session
        return session

    def open_session(
        self,
        session_id: Optional[str] = None,
        model: Optional[OntologyModel] = None,
        reasoner: Optional[Reasoner] = None,
        timeout_seconds: float = 10.0,
        max_inferences: int = 1_000_000,
        **kwargs: Any,
    ) -> Session:
        return self.create_session(
            session_id=session_id,
            model=model,
            reasoner=reasoner,
            timeout_seconds=timeout_seconds,
            max_inferences=max_inferences,
            **kwargs,
        )

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> bool:
        return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


class Engine:
    """High-level facade orchestrating sessions, querying, and validation."""

    def __init__(self) -> None:
        self.session_manager = SessionManager()
        self._prolog_available: Optional[bool] = None

    @property
    def active_backend_name(self) -> str:
        if self._prolog_available is None:
            self._prolog_available = PrologReasoner().is_available
        return "prolog" if self._prolog_available else "python"

    @property
    def available_backends(self) -> list[str]:
        if self._prolog_available is None:
            self._prolog_available = PrologReasoner().is_available
        backends = ["python"]
        if self._prolog_available:
            backends.append("prolog")
        return backends

    def query(self, model: OntologyModel, query_str: str) -> QueryResult:
        session = Session(model=model)
        results = session.execute(query_str)
        if results:
            return results[-1]
        return QueryResult(
            query_text=query_str,
            statement_type="query",
            summary="No results.",
        )
