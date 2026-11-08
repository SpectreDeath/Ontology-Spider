"""Pure-Python graph reasoner evaluating ontology queries with BFS and attribute filtering."""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Optional

from ontology_spider.model import Assertion, OntologyModel
from ontology_spider.reasoning.base import (
    Explanation,
    QueryInferenceLimitError,
    QuerySpec,
    QueryTimeoutError,
    Reasoner,
    ReasonerAnswer,
    ReasonerResult,
)


class _PythonQueryTracker:
    def __init__(self, timeout_seconds: float, max_inferences: int) -> None:
        self.deadline = (
            time.monotonic() + timeout_seconds
            if (timeout_seconds and timeout_seconds > 0)
            else float("inf")
        )
        self.max_inferences = (
            max_inferences if (max_inferences and max_inferences > 0) else 1_000_000
        )
        self.inferences = 0

    def step(self, count: int = 1) -> None:
        self.inferences += count
        if self.inferences > self.max_inferences:
            raise QueryInferenceLimitError(
                f"Query exceeded maximum inferences limit of {self.max_inferences}"
            )
        if time.monotonic() > self.deadline:
            raise QueryTimeoutError("Query exceeded timeout limit")


class PythonReasoner(Reasoner):
    """Pure Python reasoner implementing deterministic graph queries."""

    @property
    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "python"

    def query(
        self,
        model: OntologyModel,
        spec: QuerySpec | Any = "",
        goal_type: str | Any = "",
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        req_key: Optional[str] = None,
        req_val: Optional[Any] = None,
        filter_attributes: Optional[dict[str, Any]] = None,
        timeout_seconds: float = 10.0,
        max_inferences: int = 1_000_000,
        **kwargs: Any,
    ) -> ReasonerResult:
        if isinstance(spec, QuerySpec) or hasattr(spec, "kind"):
            actual_spec = spec
        elif isinstance(goal_type, QuerySpec) or hasattr(goal_type, "kind"):
            actual_spec = goal_type
        else:
            kind = str(goal_type or spec or "lookup")
            actual_spec = QuerySpec(
                kind=kind,
                subject=subject,
                predicate=predicate,
                object=object,
                filter_key=req_key,
                filter_val=req_val,
                filter_attributes=filter_attributes or {},
                timeout_seconds=float(timeout_seconds),
                max_inferences=int(max_inferences),
            )

        tracker = _PythonQueryTracker(
            actual_spec.timeout_seconds, actual_spec.max_inferences
        )

        if actual_spec.kind == "lookup":
            return self._query_lookup(model, actual_spec.subject or "", tracker)
        elif actual_spec.kind == "ancestors":
            return self._query_ancestors(model, actual_spec.subject or "", tracker)
        elif actual_spec.kind == "transitive":
            return self._query_transitive(
                model, actual_spec.subject or "", actual_spec.predicate or "", tracker
            )
        elif actual_spec.kind == "pattern":
            return self._query_pattern(
                model,
                actual_spec.subject,
                actual_spec.predicate,
                actual_spec.object,
                tracker,
            )
        elif actual_spec.kind == "filter":
            return self._query_filter(
                model,
                actual_spec.predicate or "",
                actual_spec.filter_key,
                actual_spec.filter_val,
                tracker,
            )
        elif actual_spec.kind == "recommend":
            return self._query_recommend(model, actual_spec, tracker)
        else:
            return ReasonerResult(query_goal=actual_spec.kind, answers=[])

    def _query_lookup(
        self,
        model: OntologyModel,
        subject: str,
        tracker: _PythonQueryTracker | None = None,
    ) -> ReasonerResult:
        outgoing = model.query(subject=subject)
        incoming = model.query(object=subject)
        answers: list[ReasonerAnswer] = []
        for a in outgoing + incoming:
            if tracker:
                tracker.step()
            answers.append(
                ReasonerAnswer(
                    value=f"({a.relation.subject} {a.relation.predicate} {a.relation.object})",
                    explanation=Explanation(
                        rules_fired=["direct_fact"],
                        fact_ids=[a.assertion_id],
                        path=[a.relation.subject, a.relation.object],
                        provenance_assertions=[a],
                    ),
                )
            )
        return ReasonerResult(query_goal=f"lookup({subject})", answers=answers)

    def _query_ancestors(
        self,
        model: OntologyModel,
        target: str,
        tracker: _PythonQueryTracker | None = None,
    ) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        visited: set[str] = {target}
        queue: deque[tuple[str, list[str], list[Assertion]]] = deque([(target, [target], [])])

        while queue:
            if tracker:
                tracker.step()
            curr, path, asrts = queue.popleft()
            for a in model.get_outgoing(curr):
                if tracker:
                    tracker.step()
                if a.relation.predicate in ("subclass_of", "instance_of"):
                    obj = a.relation.object
                    if obj not in visited:
                        visited.add(obj)
                        new_path = path + [obj] if len(path) < 50 else path
                        new_asrts = asrts + [a] if len(asrts) < 50 else asrts
                        queue.append((obj, new_path, new_asrts))
                        answers.append(
                            ReasonerAnswer(
                                value=obj,
                                explanation=Explanation(
                                    rules_fired=[
                                        "ancestor_rule",
                                        "degraded_python_fallback",
                                    ],
                                    fact_ids=[x.assertion_id for x in new_asrts],
                                    path=new_path,
                                    provenance_assertions=new_asrts,
                                ),
                            )
                        )
        return ReasonerResult(query_goal=f"ancestors({target})", answers=answers)

    def _query_transitive(
        self,
        model: OntologyModel,
        target: str,
        pred: str,
        tracker: _PythonQueryTracker | None = None,
    ) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        visited: set[str] = {target}
        queue: deque[tuple[str, list[str], list[Assertion]]] = deque([(target, [target], [])])

        while queue:
            if tracker:
                tracker.step()
            curr, path, asrts = queue.popleft()
            for a in model.query(subject=curr, predicate=pred):
                if tracker:
                    tracker.step()
                obj = a.relation.object
                if obj not in visited:
                    visited.add(obj)
                    new_path = path + [obj] if len(path) < 50 else path
                    new_asrts = asrts + [a] if len(asrts) < 50 else asrts
                    queue.append((obj, new_path, new_asrts))
                    answers.append(
                        ReasonerAnswer(
                            value=obj,
                            explanation=Explanation(
                                rules_fired=[
                                    "transitive_closure",
                                    "degraded_python_fallback",
                                ],
                                fact_ids=[x.assertion_id for x in new_asrts],
                                path=new_path,
                                provenance_assertions=new_asrts,
                            ),
                        )
                    )
        return ReasonerResult(
            query_goal=f"transitive({pred}, {target})", answers=answers
        )

    def _query_pattern(
        self,
        model: OntologyModel,
        subject: str | None,
        predicate: str | None,
        object_: str | None,
        tracker: _PythonQueryTracker | None = None,
    ) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        for a in model.query(subject=subject, predicate=predicate, object=object_):
            if tracker:
                tracker.step()
            answers.append(
                ReasonerAnswer(
                    value={
                        "subject": a.relation.subject,
                        "predicate": a.relation.predicate,
                        "object": a.relation.object,
                    },
                    explanation=Explanation(
                        rules_fired=["degraded_python_fallback"],
                        fact_ids=[a.assertion_id],
                        path=[a.relation.subject, a.relation.object],
                        provenance_assertions=[a],
                    ),
                )
            )
        return ReasonerResult(query_goal="pattern", answers=answers)

    def _query_filter(
        self,
        model: OntologyModel,
        predicate: str,
        filter_key: str | None,
        filter_val: Any,
        tracker: _PythonQueryTracker | None = None,
    ) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        for asrt in model.query(predicate=predicate):
            if tracker:
                tracker.step()
            val = asrt.attributes.get(filter_key) if filter_key else None
            matched = False
            if val is not None and str(val) == str(filter_val):
                matched = True
            else:
                sub_ent = model.get_entity(asrt.relation.subject)
                if sub_ent:
                    ent_val = (
                        sub_ent.attributes.get(filter_key) if filter_key else None
                    )
                    if ent_val is not None and str(ent_val) == str(filter_val):
                        matched = True
            if matched:
                answers.append(
                    ReasonerAnswer(
                        value=f"({asrt.relation.subject} {asrt.relation.predicate} {asrt.relation.object})",
                        explanation=Explanation(
                            rules_fired=["attribute_filter"],
                            fact_ids=[asrt.assertion_id],
                            path=[asrt.relation.subject, asrt.relation.object],
                            provenance_assertions=[asrt],
                        ),
                    )
                )
        return ReasonerResult(
            query_goal=f"filter({predicate}, {filter_key}={filter_val})",
            answers=answers,
        )

    def _query_recommend(
        self,
        model: OntologyModel,
        spec: QuerySpec,
        tracker: _PythonQueryTracker | None = None,
    ) -> ReasonerResult:
        cls_name = spec.object or spec.subject or ""
        ordered_target_classes: list[tuple[str, list[Assertion]]] = []
        seen_classes: set[str] = {cls_name}
        queue: list[tuple[str, list[Assertion]]] = [(cls_name, [])]
        while queue:
            if tracker:
                tracker.step()
            curr, chain = queue.pop(0)
            ordered_target_classes.append((curr, chain))
            for a in model.query(predicate="subclass_of", object=curr):
                if tracker:
                    tracker.step()
                sub = a.relation.subject
                if sub not in seen_classes:
                    seen_classes.add(sub)
                    queue.append((sub, [a] + chain))

        attrs_to_check = dict(spec.filter_attributes)
        if (
            spec.filter_key
            and spec.filter_val is not None
            and spec.filter_key not in attrs_to_check
        ):
            attrs_to_check[spec.filter_key] = spec.filter_val

        answers: list[ReasonerAnswer] = []
        seen_candidates: set[str] = set()

        for tc, chain in ordered_target_classes:
            if tracker:
                tracker.step()
            for a in model.query(predicate="instance_of", object=tc):
                if tracker:
                    tracker.step()
                cand = a.relation.subject
                if cand in seen_candidates:
                    continue

                match_all = True
                for fk, fv in attrs_to_check.items():
                    val = a.attributes.get(fk)
                    if val is None:
                        ent = model.get_entity(cand)
                        if ent:
                            val = ent.attributes.get(fk)
                    if val is None or str(val) != str(fv):
                        match_all = False
                        break

                if not match_all:
                    continue

                seen_candidates.add(cand)
                subclass_fact_ids = [sub_asrt.assertion_id for sub_asrt in chain]
                answers.append(
                    ReasonerAnswer(
                        value=cand,
                        explanation=Explanation(
                            rules_fired=[
                                "recommend",
                                "instance_of_transitive",
                                "degraded_python_fallback",
                            ],
                            fact_ids=[a.assertion_id] + subclass_fact_ids,
                            path=[cls_name, cand],
                            provenance_assertions=[a] + chain,
                        ),
                    )
                )

        return ReasonerResult(query_goal=f"recommend({cls_name})", answers=answers)
