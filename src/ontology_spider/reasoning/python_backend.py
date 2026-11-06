"""Pure-Python graph reasoner evaluating ontology queries with BFS and attribute filtering."""

from __future__ import annotations

from typing import Any

from ontology_spider.model import Assertion, OntologyModel
from ontology_spider.reasoning.base import (
    Explanation,
    QuerySpec,
    Reasoner,
    ReasonerAnswer,
    ReasonerResult,
)


class PythonReasoner(Reasoner):
    """Pure Python reasoner implementing deterministic graph queries."""

    @property
    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "python"

    def query(self, model: OntologyModel, spec: QuerySpec) -> ReasonerResult:
        if spec.kind == "lookup":
            return self._query_lookup(model, spec.subject or "")
        elif spec.kind == "ancestors":
            return self._query_ancestors(model, spec.subject or "")
        elif spec.kind == "transitive":
            return self._query_transitive(model, spec.subject or "", spec.predicate or "")
        elif spec.kind == "pattern":
            return self._query_pattern(model, spec.subject, spec.predicate, spec.object)
        elif spec.kind == "filter":
            return self._query_filter(model, spec.predicate or "", spec.filter_key, spec.filter_val)
        elif spec.kind == "recommend":
            return self._query_recommend(model, spec)
        else:
            return ReasonerResult(query_goal=spec.kind, answers=[])

    def _query_lookup(self, model: OntologyModel, subject: str) -> ReasonerResult:
        outgoing = model.query(subject=subject)
        incoming = model.query(object=subject)
        answers: list[ReasonerAnswer] = []
        for a in outgoing + incoming:
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

    def _query_ancestors(self, model: OntologyModel, target: str) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        visited: set[str] = {target}
        queue: list[tuple[str, list[str], list[Assertion]]] = [(target, [target], [])]

        while queue:
            curr, path, asrts = queue.pop(0)
            for pred in ("subclass_of", "instance_of"):
                for a in model.query(subject=curr, predicate=pred):
                    obj = a.relation.object
                    if obj not in visited:
                        visited.add(obj)
                        new_path = path + [obj]
                        new_asrts = asrts + [a]
                        queue.append((obj, new_path, new_asrts))
                        answers.append(
                            ReasonerAnswer(
                                value=obj,
                                explanation=Explanation(
                                    rules_fired=["ancestor_rule", "degraded_python_fallback"],
                                    fact_ids=[x.assertion_id for x in new_asrts],
                                    path=new_path,
                                    provenance_assertions=new_asrts,
                                    ),
                            )
                        )
        return ReasonerResult(query_goal=f"ancestors({target})", answers=answers)

    def _query_transitive(self, model: OntologyModel, target: str, pred: str) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        visited: set[str] = {target}
        queue: list[tuple[str, list[str], list[Assertion]]] = [(target, [target], [])]

        while queue:
            curr, path, asrts = queue.pop(0)
            for a in model.query(subject=curr, predicate=pred):
                obj = a.relation.object
                if obj not in visited:
                    visited.add(obj)
                    new_path = path + [obj]
                    new_asrts = asrts + [a]
                    queue.append((obj, new_path, new_asrts))
                    answers.append(
                        ReasonerAnswer(
                            value=obj,
                            explanation=Explanation(
                                rules_fired=["transitive_closure", "degraded_python_fallback"],
                                fact_ids=[x.assertion_id for x in new_asrts],
                                path=new_path,
                                provenance_assertions=new_asrts,
                            ),
                        )
                    )
        return ReasonerResult(query_goal=f"transitive({pred}, {target})", answers=answers)

    def _query_pattern(
        self,
        model: OntologyModel,
        subject: str | None,
        predicate: str | None,
        object_: str | None,
    ) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        for a in model.query(subject=subject, predicate=predicate, object=object_):
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
    ) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        for asrt in model.query(predicate=predicate):
            val = asrt.attributes.get(filter_key) if filter_key else None
            matched = False
            if val is not None and str(val) == str(filter_val):
                matched = True
            else:
                sub_ent = model.get_entity(asrt.relation.subject)
                if sub_ent:
                    ent_val = sub_ent.attributes.get(filter_key) if filter_key else None
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

    def _query_recommend(self, model: OntologyModel, spec: QuerySpec) -> ReasonerResult:
        cls_name = spec.object or spec.subject or ""
        target_classes = {cls_name}
        queue = [cls_name]
        while queue:
            curr = queue.pop(0)
            for a in model.query(predicate="subclass_of", object=curr):
                sub = a.relation.subject
                if sub not in target_classes:
                    target_classes.add(sub)
                    queue.append(sub)

        attrs_to_check = dict(spec.filter_attributes)
        if spec.filter_key and spec.filter_val is not None and spec.filter_key not in attrs_to_check:
            attrs_to_check[spec.filter_key] = spec.filter_val

        answers: list[ReasonerAnswer] = []
        seen_candidates: set[str] = set()

        for tc in target_classes:
            for a in model.query(predicate="instance_of", object=tc):
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
                answers.append(
                    ReasonerAnswer(
                        value=cand,
                        explanation=Explanation(
                            rules_fired=["recommend", "instance_of_transitive", "degraded_python_fallback"],
                            fact_ids=[a.assertion_id],
                            path=[cls_name, cand],
                            provenance_assertions=[a],
                        ),
                    )
                )

        return ReasonerResult(query_goal=f"recommend({cls_name})", answers=answers)
