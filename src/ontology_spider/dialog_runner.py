"""Turn-by-turn execution of .dialog scripts and interactive sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

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
from ontology_spider.prolog.reasoner import (
    Explanation,
    PrologReasoner,
    PrologUnavailableError,
    ReasonerAnswer,
    ReasonerResult,
)
from ontology_spider.seam import DialogModelSource, JsonModelSource


@dataclass
class DialogTurnResult:
    """Outcome of running a single statement or turn."""
    statement_type: str  # "import", "assertion", "query", "explain"
    summary_text: str
    answers: list[ReasonerAnswer] = field(default_factory=list)
    raw_query: Optional[DialogQuery] = None


class DialogSession:
    """Manages an active dialog session with state, history, and reasoner integration."""

    def __init__(
        self,
        model: Optional[OntologyModel] = None,
        reasoner: Optional[PrologReasoner] = None,
        base_dir: Optional[Path] = None,
        allow_degraded_fallback: bool = True,
    ) -> None:
        self.model = model or OntologyModel(uri="urn:dialog:session")
        self.reasoner = reasoner or PrologReasoner()
        self.base_dir = base_dir or Path.cwd()
        self.allow_degraded_fallback = allow_degraded_fallback
        self.turn_counter: int = 0
        self.last_query_result: Optional[ReasonerResult] = None
        self.history: list[DialogTurnResult] = []

    def execute_statement(
        self,
        stmt: Union[DialogImport, DialogEntityDecl, DialogAssertion, DialogQuery],
    ) -> DialogTurnResult:
        self.turn_counter += 1
        turn_id = f"turn_{self.turn_counter}"

        if isinstance(stmt, DialogImport):
            target_path = Path(stmt.path)
            if not target_path.is_absolute():
                target_path = self.base_dir / target_path

            if target_path.suffix.lower() == ".json":
                sub_model = JsonModelSource(target_path).load()
            elif target_path.suffix.lower() == ".dialog":
                sub_model = DialogModelSource(target_path).load()
            else:
                raise ValueError(f"Unsupported model import format: {target_path}")

            for ent in sub_model.entities.values():
                self.model.add_entity(ent)
            for asrt in sub_model.assertions.values():
                self.model.add_assertion(
                    relation=asrt.relation,
                    provenance=asrt.provenance,
                    assertion_id=asrt.assertion_id,
                    attributes=asrt.attributes,
                )

            res = DialogTurnResult(
                statement_type="import",
                summary_text=f"Imported model from {target_path.name} ({len(sub_model.assertions)} assertions)",
            )
            self.history.append(res)
            return res

        if isinstance(stmt, DialogEntityDecl):
            ent_attrs = dict(stmt.attributes)
            name = ent_attrs.pop("name", None)
            existing = self.model.get_entity(stmt.entity_id)
            if existing:
                existing.attributes.update(ent_attrs)
                if name:
                    existing.name = name
            else:
                self.model.add_entity(
                    Entity(id=stmt.entity_id, name=name, attributes=ent_attrs)
                )
            res = DialogTurnResult(
                statement_type="entity",
                summary_text=f"Declared entity: {stmt.entity_id} with {len(stmt.attributes)} attributes",
            )
            self.history.append(res)
            return res

        if isinstance(stmt, DialogAssertion):
            attrs = dict(stmt.attributes)
            aid = attrs.pop("_id", None)
            src = attrs.pop("_source", "dialog_session")
            tid = attrs.pop("_turn", turn_id)
            prov = Provenance(
                source=src,
                turn_id=tid,
            )
            asrt = self.model.add_assertion(
                relation=Relation(stmt.subject, stmt.predicate, stmt.object),
                provenance=prov,
                assertion_id=aid,
                attributes=attrs,
            )
            res = DialogTurnResult(
                statement_type="assertion",
                summary_text=f"Asserted: ({stmt.subject} {stmt.predicate} {stmt.object}) [{asrt.assertion_id}]",
            )
            self.history.append(res)
            return res

        if isinstance(stmt, DialogQuery):
            res = self._execute_query(stmt, turn_id)
            self.history.append(res)
            return res

        raise ValueError(f"Unknown statement type: {type(stmt)}")

    def _coerce_val(self, val: Any) -> Any:
        if val is None:
            return None
        s = str(val).strip().strip('"').strip("'")
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    def _execute_degraded_query(self, query: DialogQuery) -> ReasonerResult:
        answers: list[ReasonerAnswer] = []
        if query.kind == "ancestors":
            target = query.subject
            visited: set[str] = {target}
            queue: list[tuple[str, list[str], list[Assertion]]] = [(target, [target], [])]
            while queue:
                curr, path, asrts = queue.pop(0)
                for pred in ("subclass_of", "instance_of"):
                    for a in self.model.query(subject=curr, predicate=pred):
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

        if query.kind == "transitive":
            target = query.subject
            pred = query.predicate
            visited: set[str] = {target}
            queue: list[tuple[str, list[str], list[Assertion]]] = [(target, [target], [])]
            while queue:
                curr, path, asrts = queue.pop(0)
                for a in self.model.query(subject=curr, predicate=pred):
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

        if query.kind == "pattern":
            for a in self.model.query(
                subject=query.subject, predicate=query.predicate, object=query.object
            ):
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

        if query.kind == "recommend":
            cls_name = query.object or query.subject or ""
            target_classes = {cls_name}
            queue = [cls_name]
            while queue:
                curr = queue.pop(0)
                for a in self.model.query(predicate="subclass_of", object=curr):
                    sub = a.relation.subject
                    if sub not in target_classes:
                        target_classes.add(sub)
                        queue.append(sub)

            for tc in target_classes:
                for a in self.model.query(predicate="instance_of", object=tc):
                    cand = a.relation.subject
                    if query.filter_key and query.filter_val is not None:
                        val = a.attributes.get(query.filter_key)
                        if val is None:
                            ent = self.model.get_entity(cand)
                            if ent:
                                val = ent.attributes.get(query.filter_key)
                        if val is None or str(val) != str(query.filter_val):
                            continue
                    answers.append(
                        ReasonerAnswer(
                            value=cand,
                            explanation=Explanation(
                                rules_fired=["degraded_python_fallback"],
                                fact_ids=[a.assertion_id],
                                path=[cls_name, cand],
                                provenance_assertions=[a],
                            ),
                        )
                    )
            return ReasonerResult(query_goal=f"recommend({cls_name})", answers=answers)

        return ReasonerResult(query_goal=query.kind, answers=[])

    def _execute_query(self, query: DialogQuery, turn_id: str) -> DialogTurnResult:
        if query.kind == "explain":
            if query.subquery is not None:
                self._execute_query(query.subquery, turn_id)

            if not self.last_query_result or not self.last_query_result.answers:
                return DialogTurnResult(
                    statement_type="explain",
                    summary_text="No preceding query answer to explain.",
                    raw_query=query,
                )
            lines = ["Explanation for previous answers:"]
            for idx, ans in enumerate(self.last_query_result.answers, start=1):
                lines.append(f"Answer #{idx} [{ans.value}]:")
                exp_summary = ans.explanation.summary()
                for exp_line in exp_summary.splitlines():
                    lines.append(f"  {exp_line}")

            return DialogTurnResult(
                statement_type="explain",
                summary_text="\n".join(lines),
                answers=self.last_query_result.answers,
                raw_query=query,
            )

        # Query kinds: lookup, ancestors, transitive, filter, pattern, recommend
        if query.kind == "lookup":
            # Direct entity lookup: find all relations where entity is subject or object
            subject = query.subject
            outgoing = self.model.query(subject=subject)
            incoming = self.model.query(object=subject)

            answers: list[ReasonerAnswer] = []
            for a in outgoing:
                ans = ReasonerAnswer(
                    value=f"({a.relation.subject} {a.relation.predicate} {a.relation.object})",
                    explanation=Explanation(
                        rules_fired=["direct_fact"],
                        fact_ids=[a.assertion_id],
                        path=[a.relation.subject, a.relation.object],
                        provenance_assertions=[a],
                    ),
                )
                answers.append(ans)
            for a in incoming:
                ans = ReasonerAnswer(
                    value=f"({a.relation.subject} {a.relation.predicate} {a.relation.object})",
                    explanation=Explanation(
                        rules_fired=["direct_fact"],
                        fact_ids=[a.assertion_id],
                        path=[a.relation.subject, a.relation.object],
                        provenance_assertions=[a],
                    ),
                )
                answers.append(ans)

            reasoner_res = ReasonerResult(
                query_goal=f"lookup({subject})",
                answers=answers,
            )
            self.last_query_result = reasoner_res
            summary = f"Found {len(answers)} facts for '{subject}'."
            return DialogTurnResult(
                statement_type="query",
                summary_text=summary,
                answers=answers,
                raw_query=query,
            )

        if query.kind == "ancestors":
            if not self.reasoner.is_available:
                if not self.allow_degraded_fallback:
                    raise PrologUnavailableError("SWI-Prolog (swipl) was not found.")
                reasoner_res = self._execute_degraded_query(query)
                prefix = "[Degraded Mode: swipl unavailable] "
            else:
                reasoner_res = self.reasoner.query(
                    self.model, goal_type="ancestors", subject=query.subject
                )
                prefix = ""
            self.last_query_result = reasoner_res
            vals = [str(a.value) for a in reasoner_res.answers]
            summary = f"{prefix}Ancestors of {query.subject}: {', '.join(vals) if vals else 'none'}"
            return DialogTurnResult(
                statement_type="query",
                summary_text=summary,
                answers=reasoner_res.answers,
                raw_query=query,
            )

        if query.kind == "transitive":
            if not self.reasoner.is_available:
                if not self.allow_degraded_fallback:
                    raise PrologUnavailableError("SWI-Prolog (swipl) was not found.")
                reasoner_res = self._execute_degraded_query(query)
                prefix = "[Degraded Mode: swipl unavailable] "
            else:
                reasoner_res = self.reasoner.query(
                    self.model,
                    goal_type="transitive",
                    subject=query.subject,
                    predicate=query.predicate,
                )
                prefix = ""
            self.last_query_result = reasoner_res
            vals = [str(a.value) for a in reasoner_res.answers]
            summary = f"{prefix}Transitive {query.predicate} from {query.subject}: {', '.join(vals) if vals else 'none'}"
            return DialogTurnResult(
                statement_type="query",
                summary_text=summary,
                answers=reasoner_res.answers,
                raw_query=query,
            )

        if query.kind == "recommend":
            cls_name = query.object or query.subject or ""
            f_val = self._coerce_val(query.filter_val) if query.filter_val is not None else None
            if not self.reasoner.is_available:
                if not self.allow_degraded_fallback:
                    raise PrologUnavailableError("SWI-Prolog (swipl) was not found.")
                reasoner_res = self._execute_degraded_query(query)
                prefix = "[Degraded Mode: swipl unavailable] "
            else:
                reasoner_res = self.reasoner.query(
                    self.model,
                    goal_type="recommend",
                    subject=cls_name,
                    req_key=query.filter_key,
                    req_val=f_val,
                )
                prefix = ""
            self.last_query_result = reasoner_res
            vals = [str(a.value) for a in reasoner_res.answers]
            filter_info = (
                f" where {query.filter_key}={query.filter_val}"
                if query.filter_key
                else ""
            )
            summary = f"{prefix}Recommended {cls_name}{filter_info}: {', '.join(vals) if vals else 'none'}"
            return DialogTurnResult(
                statement_type="query",
                summary_text=summary,
                answers=reasoner_res.answers,
                raw_query=query,
            )

        if query.kind == "filter":
            # Match assertions by predicate and attribute
            matching: list[Assertion] = []
            for asrt in self.model.query(predicate=query.predicate):
                val = asrt.attributes.get(query.filter_key)
                if val is not None and str(val) == str(query.filter_val):
                    matching.append(asrt)
                    continue
                # Check entity attributes as well
                sub_ent = self.model.get_entity(asrt.relation.subject)
                if sub_ent:
                    ent_val = sub_ent.attributes.get(query.filter_key)
                    if ent_val is not None and str(ent_val) == str(query.filter_val):
                        matching.append(asrt)

            answers = [
                ReasonerAnswer(
                    value=f"({a.relation.subject} {a.relation.predicate} {a.relation.object})",
                    explanation=Explanation(
                        rules_fired=["attribute_filter"],
                        fact_ids=[a.assertion_id],
                        path=[a.relation.subject, a.relation.object],
                        provenance_assertions=[a],
                    ),
                )
                for a in matching
            ]
            reasoner_res = ReasonerResult(
                query_goal=f"filter({query.predicate}, {query.filter_key}={query.filter_val})",
                answers=answers,
            )
            self.last_query_result = reasoner_res
            summary = f"Filtered {query.predicate} ({query.filter_key}={query.filter_val}): {len(answers)} matches"
            return DialogTurnResult(
                statement_type="query",
                summary_text=summary,
                answers=answers,
                raw_query=query,
            )


        if query.kind == "pattern":
            if not self.reasoner.is_available:
                if not self.allow_degraded_fallback:
                    raise PrologUnavailableError("SWI-Prolog (swipl) was not found.")
                reasoner_res = self._execute_degraded_query(query)
                prefix = "[Degraded Mode: swipl unavailable] "
            else:
                reasoner_res = self.reasoner.query(
                    self.model,
                    goal_type="pattern",
                    subject=query.subject,
                    predicate=query.predicate,
                    object=query.object,
                )
                prefix = ""
            self.last_query_result = reasoner_res
            matched_triples = [
                f"({ans.value.get('subject')} {ans.value.get('predicate')} {ans.value.get('object')})"
                for ans in reasoner_res.answers
            ]
            summary = f"{prefix}Matches: {', '.join(matched_triples) if matched_triples else 'none'}"
            return DialogTurnResult(
                statement_type="query",
                summary_text=summary,
                answers=reasoner_res.answers,
                raw_query=query,
            )


        raise ValueError(f"Unsupported query kind: {query.kind}")

    def run_text(self, text: str) -> list[DialogTurnResult]:
        """Execute a full dialog script text."""
        doc = parse_dialog(text)
        results = []
        for stmt in doc.statements:
            results.append(self.execute_statement(stmt))
        return results

    def run_file(self, path: Union[str, Path]) -> list[DialogTurnResult]:
        """Execute a dialog script from file."""
        file_path = Path(path)
        text = file_path.read_text(encoding="utf-8")
        self.base_dir = file_path.parent
        return self.run_text(text)
