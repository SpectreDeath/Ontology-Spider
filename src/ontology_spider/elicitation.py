"""Managed elicitation state machine with mixed-initiative correction and provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from ontology_spider.dialog import _parse_attributes, parse_dialog
from ontology_spider.dialog_runner import DialogSession
from ontology_spider.model import (
    ACYCLIC,
    DISJOINT_WITH,
    DOMAIN,
    INSTANCE_OF,
    RANGE,
    SUBCLASS_OF,
    Assertion,
    Entity,
    OntologyModel,
    Provenance,
    Relation,
)


class ElicitationState(Enum):
    DECISION_QUESTION = "decision_question"
    COMPETENCY_QUESTIONS = "competency_questions"
    ELICIT_CLASSES = "elicit_classes"
    ELICIT_RELATIONS = "elicit_relations"
    ELICIT_INSTANCES = "elicit_instances"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"


@dataclass
class ElicitedTurn:
    """A single recorded elicitation turn with dependency tracking."""
    turn_id: str
    state: ElicitationState
    prompt: str
    user_response: str = ""
    proposed_assertions: list[Assertion] = field(default_factory=list)
    proposed_entities: dict[str, dict[str, Any]] = field(default_factory=dict)
    depends_on_turn_ids: list[str] = field(default_factory=list)
    confirmed: bool = False
    phase: Optional[ElicitationState] = None


class ElicitationManager:
    """Dialogue manager turning conversational knowledge acquisition into an ontology."""

    def __init__(
        self,
        uri: str = "urn:ontology:elicited",
        validation_hook: Optional[Callable[[OntologyModel], list[str]]] = None,
    ) -> None:
        self.uri = uri
        self.model = OntologyModel(uri=uri)
        self.state = ElicitationState.DECISION_QUESTION
        self.scope_description: str = ""
        self.competency_queries: list[str] = []
        self.turns: list[ElicitedTurn] = []
        self.pending_turn: Optional[ElicitedTurn] = None
        self.pending_reconfirmations: list[ElicitedTurn] = []
        self.validation_hook = validation_hook
        self._turn_counter = 0
        self._symbol_turn_map: dict[str, str] = {}
        self.current_prompt: str = ""
        self.start()

    @property
    def stage(self) -> ElicitationState:
        return self.state

    def prompt(self) -> str:
        """Return the current prompt string for the user."""
        if self.pending_reconfirmations:
            return self.current_prompt
        if self.pending_turn:
            return self.pending_turn.prompt
        if self.current_prompt:
            return self.current_prompt
        return ""

    def handle_input(self, user_input: str) -> str:
        """Process user input against current state."""
        return self.step(user_input)

    def _next_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn_{self._turn_counter}"

    def start(self) -> str:
        """Start the elicitation dialogue."""
        prompt = "What domain or topic is this ontology about? (Decision Question)"
        if not self.pending_turn:
            self.pending_turn = ElicitedTurn(
                turn_id=self._next_turn_id(),
                state=ElicitationState.DECISION_QUESTION,
                prompt=prompt,
                phase=ElicitationState.DECISION_QUESTION,
            )
        self.current_prompt = prompt
        return prompt

    def step(self, user_input: str) -> str:
        """Process user input against current state by delegating to state handlers."""
        clean = user_input.strip()

        # Handle pending re-confirmations from earlier amendments first
        if self.pending_reconfirmations:
            return self._handle_reconfirmations(clean)

        if self.state == ElicitationState.DECISION_QUESTION:
            return self._step_decision_question(clean)
        elif self.state == ElicitationState.COMPETENCY_QUESTIONS:
            return self._step_competency_questions(clean)
        elif self.state == ElicitationState.ELICIT_CLASSES:
            return self._step_elicit_classes(clean)
        elif self.state == ElicitationState.ELICIT_RELATIONS:
            return self._step_elicit_relations(clean)
        elif self.state == ElicitationState.ELICIT_INSTANCES:
            return self._step_elicit_instances(clean)
        elif self.state == ElicitationState.CONFIRMATION:
            return self._step_confirmation(clean)

        return "Elicitation completed."

    def _handle_reconfirmations(self, clean: str) -> str:
        reconf_turn = self.pending_reconfirmations.pop(0)
        if clean.lower() in ("y", "yes", "confirm"):
            reconf_turn.confirmed = True
            for ent_id, ent_attrs in reconf_turn.proposed_entities.items():
                self.model.upsert_entity(ent_id, attributes=ent_attrs)
            for asrt in reconf_turn.proposed_assertions:
                self.model.add_assertion(
                    relation=asrt.relation,
                    provenance=asrt.provenance,
                    assertion_id=asrt.assertion_id,
                    attributes=asrt.attributes,
                )
            msg = f"Re-confirmed turn '{reconf_turn.turn_id}'."
        else:
            self.turns = [t for t in self.turns if t.turn_id != reconf_turn.turn_id]
            msg = f"Turn '{reconf_turn.turn_id}' discarded."

        if self.pending_reconfirmations:
            next_turn = self.pending_reconfirmations[0]
            self.current_prompt = (
                f"{msg} Confirm next downstream turn '{next_turn.turn_id}': "
                f"'{next_turn.user_response}'? (y/n)"
            )
            return self.current_prompt
        else:
            self.current_prompt = (
                f"{msg} All re-confirmations resolved. Continuing in {self.state.value}."
            )
            return self.current_prompt

    def _step_decision_question(self, clean: str) -> str:
        self.scope_description = clean
        if self.pending_turn:
            self.pending_turn.user_response = clean
            self.pending_turn.confirmed = True
            self.turns.append(self.pending_turn)

        self.state = ElicitationState.COMPETENCY_QUESTIONS
        prompt = (
            f"Scope set: '{clean}'.\n"
            "What competency question should this ontology answer? "
            "(e.g. 'query ancestors of cat' or 'done' to move to classes)"
        )
        self.pending_turn = ElicitedTurn(
            turn_id=self._next_turn_id(),
            state=ElicitationState.COMPETENCY_QUESTIONS,
            prompt=prompt,
            phase=ElicitationState.COMPETENCY_QUESTIONS,
        )
        self.current_prompt = prompt
        return prompt

    def _step_competency_questions(self, clean: str) -> str:
        if clean.lower() in ("done", "none", "skip"):
            self.state = ElicitationState.ELICIT_CLASSES
            prompt = (
                "Enter class hierarchies (e.g. 'cat subclass_of mammal', "
                "'air_vehicle disjoint_with ground_vehicle' or 'done'):"
            )
            self.pending_turn = ElicitedTurn(
                turn_id=self._next_turn_id(),
                state=ElicitationState.ELICIT_CLASSES,
                prompt=prompt,
                phase=ElicitationState.ELICIT_CLASSES,
            )
            self.current_prompt = prompt
            return prompt

        # Record competency question
        self.competency_queries.append(clean)
        self.current_prompt = "Competency query recorded. Enter another or 'done':"
        return self.current_prompt

    def _step_elicit_classes(self, clean: str) -> str:
        if clean.lower() in ("done", "skip"):
            self.state = ElicitationState.ELICIT_RELATIONS
            prompt = (
                "Enter relation constraints (e.g. 'eats domain=animal range=food', "
                "'part_of acyclic=true' or 'done'):"
            )
            self.pending_turn = ElicitedTurn(
                turn_id=self._next_turn_id(),
                state=ElicitationState.ELICIT_RELATIONS,
                prompt=prompt,
                phase=ElicitationState.ELICIT_RELATIONS,
            )
            self.current_prompt = prompt
            return prompt

        # Parse class assertion: <subclass> subclass_of <superclass> OR <c1> disjoint_with <c2>
        tokens = clean.split()
        if len(tokens) == 3 and tokens[1] == "subclass_of":
            sub, _, sup = tokens
            turn_id = self._next_turn_id()
            prov = Provenance(source="elicitation", turn_id=turn_id)
            asrt = Assertion(
                assertion_id=f"asrt_{turn_id}",
                relation=Relation(sub, SUBCLASS_OF, sup),
                provenance=prov,
            )
            deps = []
            if sup in self._symbol_turn_map:
                deps.append(self._symbol_turn_map[sup])

            self.pending_turn = ElicitedTurn(
                turn_id=turn_id,
                state=ElicitationState.CONFIRMATION,
                prompt=f"Please confirm: assert ({sub} subclass_of {sup})? (y/n)",
                user_response=clean,
                proposed_assertions=[asrt],
                depends_on_turn_ids=deps,
                phase=ElicitationState.ELICIT_CLASSES,
            )
            self.state = ElicitationState.CONFIRMATION
            self.current_prompt = self.pending_turn.prompt
            return self.current_prompt
        elif len(tokens) == 3 and tokens[1] == "disjoint_with":
            c1, _, c2 = tokens
            turn_id = self._next_turn_id()
            prov = Provenance(source="elicitation", turn_id=turn_id)
            asrt = Assertion(
                assertion_id=f"asrt_{turn_id}",
                relation=Relation(c1, DISJOINT_WITH, c2),
                provenance=prov,
            )
            deps = []
            if c1 in self._symbol_turn_map:
                deps.append(self._symbol_turn_map[c1])
            if c2 in self._symbol_turn_map and self._symbol_turn_map[c2] not in deps:
                deps.append(self._symbol_turn_map[c2])

            self.pending_turn = ElicitedTurn(
                turn_id=turn_id,
                state=ElicitationState.CONFIRMATION,
                prompt=f"Please confirm: assert ({c1} disjoint_with {c2})? (y/n)",
                user_response=clean,
                proposed_assertions=[asrt],
                depends_on_turn_ids=deps,
                phase=ElicitationState.ELICIT_CLASSES,
            )
            self.state = ElicitationState.CONFIRMATION
            self.current_prompt = self.pending_turn.prompt
            return self.current_prompt
        else:
            self.current_prompt = (
                "Invalid class format. Expected: '<child> subclass_of <parent>', "
                "'<c1> disjoint_with <c2>', or 'done'."
            )
            return self.current_prompt

    def _step_elicit_relations(self, clean: str) -> str:
        if clean.lower() in ("done", "skip"):
            self.state = ElicitationState.ELICIT_INSTANCES
            prompt = (
                "Enter instances (e.g. 'felix instance_of cat [color=black]', "
                "'felix eats fish' or 'done'):"
            )
            self.pending_turn = ElicitedTurn(
                turn_id=self._next_turn_id(),
                state=ElicitationState.ELICIT_INSTANCES,
                prompt=prompt,
                phase=ElicitationState.ELICIT_INSTANCES,
            )
            self.current_prompt = prompt
            return prompt

        tokens = clean.split()
        rel_name = tokens[0]
        turn_id = self._next_turn_id()
        prov = Provenance(source="elicitation", turn_id=turn_id)
        proposed: list[Assertion] = []
        deps = []

        for param in tokens[1:]:
            if param.startswith("domain="):
                d_val = param.split("=", 1)[1]
                if d_val in self._symbol_turn_map and self._symbol_turn_map[d_val] not in deps:
                    deps.append(self._symbol_turn_map[d_val])
                proposed.append(
                    Assertion(
                        assertion_id=f"asrt_{turn_id}_dom",
                        relation=Relation(rel_name, DOMAIN, d_val),
                        provenance=prov,
                    )
                )
            elif param.startswith("range="):
                r_val = param.split("=", 1)[1]
                if r_val in self._symbol_turn_map and self._symbol_turn_map[r_val] not in deps:
                    deps.append(self._symbol_turn_map[r_val])
                proposed.append(
                    Assertion(
                        assertion_id=f"asrt_{turn_id}_rng",
                        relation=Relation(rel_name, RANGE, r_val),
                        provenance=prov,
                    )
                )
            elif param.lower() == "acyclic=true":
                proposed.append(
                    Assertion(
                        assertion_id=f"asrt_{turn_id}_acy",
                        relation=Relation(rel_name, ACYCLIC, "true"),
                        provenance=prov,
                    )
                )

        if not proposed:
            self.current_prompt = (
                "No valid domain/range/acyclic specs found. "
                "Format: '<rel> domain=<D> range=<R>' or 'done'."
            )
            return self.current_prompt

        self.pending_turn = ElicitedTurn(
            turn_id=turn_id,
            state=ElicitationState.CONFIRMATION,
            prompt=f"Please confirm {len(proposed)} relation properties for '{rel_name}'? (y/n)",
            user_response=clean,
            proposed_assertions=proposed,
            depends_on_turn_ids=deps,
            phase=ElicitationState.ELICIT_RELATIONS,
        )
        self.state = ElicitationState.CONFIRMATION
        self.current_prompt = self.pending_turn.prompt
        return self.current_prompt

    def _step_elicit_instances(self, clean: str) -> str:
        if clean.lower() in ("done", "skip"):
            self.state = ElicitationState.COMPLETED
            return self._finalize_elicitation()

        # Parse optional bracketed attributes [k=v, ...]
        attrs: dict[str, Any] = {}
        core_line = clean
        if "[" in clean and clean.endswith("]"):
            bracket_idx = clean.find("[")
            attr_str = clean[bracket_idx:]
            core_line = clean[:bracket_idx].strip()
            try:
                attrs = _parse_attributes(attr_str, 0)
            except Exception:
                attrs = {}

        tokens = core_line.split()
        if len(tokens) == 3 and tokens[1] in (INSTANCE_OF, "instance_of"):
            inst, _, cls_name = tokens
            turn_id = self._next_turn_id()
            prov = Provenance(source="elicitation", turn_id=turn_id)
            asrt = Assertion(
                assertion_id=f"asrt_{turn_id}",
                relation=Relation(inst, INSTANCE_OF, cls_name),
                provenance=prov,
                attributes=attrs,
            )
            deps = []
            if cls_name in self._symbol_turn_map:
                deps.append(self._symbol_turn_map[cls_name])

            proposed_entities = {}
            if attrs:
                proposed_entities[inst] = attrs

            self.pending_turn = ElicitedTurn(
                turn_id=turn_id,
                state=ElicitationState.CONFIRMATION,
                prompt=f"Please confirm: assert ({inst} instance_of {cls_name})? (y/n)",
                user_response=clean,
                proposed_assertions=[asrt],
                proposed_entities=proposed_entities,
                depends_on_turn_ids=deps,
                phase=ElicitationState.ELICIT_INSTANCES,
            )
            self.state = ElicitationState.CONFIRMATION
            self.current_prompt = self.pending_turn.prompt
            return self.current_prompt
        elif len(tokens) == 3:
            s, p, o = tokens
            turn_id = self._next_turn_id()
            prov = Provenance(source="elicitation", turn_id=turn_id)
            asrt = Assertion(
                assertion_id=f"asrt_{turn_id}",
                relation=Relation(s, p, o),
                provenance=prov,
                attributes=attrs,
            )
            deps = []
            for sym in (s, p, o):
                if sym in self._symbol_turn_map and self._symbol_turn_map[sym] not in deps:
                    deps.append(self._symbol_turn_map[sym])

            self.pending_turn = ElicitedTurn(
                turn_id=turn_id,
                state=ElicitationState.CONFIRMATION,
                prompt=f"Please confirm: assert ({s} {p} {o})? (y/n)",
                user_response=clean,
                proposed_assertions=[asrt],
                depends_on_turn_ids=deps,
                phase=ElicitationState.ELICIT_INSTANCES,
            )
            self.state = ElicitationState.CONFIRMATION
            self.current_prompt = self.pending_turn.prompt
            return self.current_prompt
        else:
            self.current_prompt = (
                "Invalid instance assertion. Expected '<item> instance_of <class> [k=v]' "
                "or '<s p o> [k=v]' or 'done'."
            )
            return self.current_prompt

    def _step_confirmation(self, clean: str) -> str:
        if clean.lower() in ("y", "yes", "confirm"):
            if self.pending_turn:
                self.pending_turn.confirmed = True
                for ent_id, ent_attrs in self.pending_turn.proposed_entities.items():
                    self.model.upsert_entity(ent_id, attributes=ent_attrs)

                for asrt in self.pending_turn.proposed_assertions:
                    self.model.add_assertion(
                        relation=asrt.relation,
                        provenance=asrt.provenance,
                        assertion_id=asrt.assertion_id,
                        attributes=asrt.attributes,
                    )
                    # Register symbols
                    rel = asrt.relation
                    if rel.predicate in (SUBCLASS_OF, DISJOINT_WITH):
                        self._symbol_turn_map.setdefault(rel.subject, self.pending_turn.turn_id)
                        self._symbol_turn_map.setdefault(rel.object, self.pending_turn.turn_id)
                    elif rel.predicate in (DOMAIN, RANGE, ACYCLIC):
                        self._symbol_turn_map.setdefault(rel.subject, self.pending_turn.turn_id)
                    elif rel.predicate == INSTANCE_OF:
                        self._symbol_turn_map.setdefault(rel.subject, self.pending_turn.turn_id)
                    else:
                        self._symbol_turn_map.setdefault(rel.predicate, self.pending_turn.turn_id)

                self.turns.append(self.pending_turn)

            prev_state = self._determine_next_state_after_confirmation()
            self.state = prev_state
            self.pending_turn = None
            self.current_prompt = "Confirmed and landed in model. Enter next or 'done':"
            return self.current_prompt
        else:
            rejected_id = self.pending_turn.turn_id if self.pending_turn else "unknown"
            prev_state = self._determine_next_state_after_confirmation()
            self.state = prev_state
            self.pending_turn = None
            self.current_prompt = f"Turn {rejected_id} discarded (not confirmed). Enter next or 'done':"
            return self.current_prompt

        return "Elicitation completed."

    def _determine_next_state_after_confirmation(self) -> ElicitationState:
        if self.pending_turn and self.pending_turn.phase:
            return self.pending_turn.phase
        if not self.pending_turn or not self.pending_turn.proposed_assertions:
            return ElicitationState.ELICIT_INSTANCES
        first_rel = self.pending_turn.proposed_assertions[0].relation.predicate
        if first_rel in (SUBCLASS_OF, DISJOINT_WITH):
            return ElicitationState.ELICIT_CLASSES
        if first_rel in (DOMAIN, RANGE, ACYCLIC):
            return ElicitationState.ELICIT_RELATIONS
        return ElicitationState.ELICIT_INSTANCES

    def amend_turn(self, turn_id: str, new_input: str) -> str:
        """Mixed-initiative correction: amend an earlier answer, retracting dependent assertions."""
        target_turn = next((t for t in self.turns if t.turn_id == turn_id), None)
        if not target_turn:
            return f"Error: turn '{turn_id}' not found."

        # Retract target assertions from model
        retracted = self.model.retract_by_turn_id(turn_id)

        # Transitive dependents calculation
        invalidated: list[ElicitedTurn] = []
        queue = [turn_id]
        seen_ids = set()
        while queue:
            curr_id = queue.pop(0)
            for t in self.turns:
                if curr_id in t.depends_on_turn_ids and t.turn_id not in seen_ids and t.turn_id != turn_id:
                    seen_ids.add(t.turn_id)
                    invalidated.append(t)
                    queue.append(t.turn_id)

        turn_order = {t.turn_id: idx for idx, t in enumerate(self.turns)}
        invalidated.sort(key=lambda t: turn_order.get(t.turn_id, 0))

        for dt in invalidated:
            retracted.extend(self.model.retract_by_turn_id(dt.turn_id))
            dt.confirmed = False

        # Parse new input and apply to target_turn
        prov = Provenance(source="elicitation", turn_id=turn_id)
        phase = target_turn.phase or ElicitationState.ELICIT_CLASSES
        applied_msg = ""

        if phase == ElicitationState.ELICIT_CLASSES:
            tokens = new_input.strip().split()
            if len(tokens) == 3 and tokens[1] == "subclass_of":
                sub, _, sup = tokens
                asrt = Assertion(
                    assertion_id=f"asrt_{turn_id}",
                    relation=Relation(sub, SUBCLASS_OF, sup),
                    provenance=prov,
                )
                target_turn.proposed_assertions = [asrt]
                target_turn.user_response = new_input
                target_turn.confirmed = True
                self.model.add_assertion(
                    relation=asrt.relation,
                    provenance=asrt.provenance,
                    assertion_id=asrt.assertion_id,
                )
                self._symbol_turn_map.setdefault(sub, turn_id)
                self._symbol_turn_map.setdefault(sup, turn_id)
                applied_msg = f"Applied replacement class hierarchy: ({sub} subclass_of {sup})."
            elif len(tokens) == 3 and tokens[1] == "disjoint_with":
                c1, _, c2 = tokens
                asrt = Assertion(
                    assertion_id=f"asrt_{turn_id}",
                    relation=Relation(c1, DISJOINT_WITH, c2),
                    provenance=prov,
                )
                target_turn.proposed_assertions = [asrt]
                target_turn.user_response = new_input
                target_turn.confirmed = True
                self.model.add_assertion(
                    relation=asrt.relation,
                    provenance=asrt.provenance,
                    assertion_id=asrt.assertion_id,
                )
                self._symbol_turn_map.setdefault(c1, turn_id)
                self._symbol_turn_map.setdefault(c2, turn_id)
                applied_msg = f"Applied replacement disjointness: ({c1} disjoint_with {c2})."

        elif phase == ElicitationState.ELICIT_RELATIONS:
            tokens = new_input.strip().split()
            rel_name = tokens[0]
            new_asrts = []
            for param in tokens[1:]:
                if param.startswith("domain="):
                    d_val = param.split("=", 1)[1]
                    new_asrts.append(
                        Assertion(
                            assertion_id=f"asrt_{turn_id}_dom",
                            relation=Relation(rel_name, DOMAIN, d_val),
                            provenance=prov,
                        )
                    )
                elif param.startswith("range="):
                    r_val = param.split("=", 1)[1]
                    new_asrts.append(
                        Assertion(
                            assertion_id=f"asrt_{turn_id}_rng",
                            relation=Relation(rel_name, RANGE, r_val),
                            provenance=prov,
                        )
                    )
                elif param.lower() == "acyclic=true":
                    new_asrts.append(
                        Assertion(
                            assertion_id=f"asrt_{turn_id}_acy",
                            relation=Relation(rel_name, ACYCLIC, "true"),
                            provenance=prov,
                        )
                    )
            target_turn.proposed_assertions = new_asrts
            target_turn.user_response = new_input
            target_turn.confirmed = True
            for a in new_asrts:
                self.model.add_assertion(
                    relation=a.relation,
                    provenance=a.provenance,
                    assertion_id=a.assertion_id,
                )
            self._symbol_turn_map.setdefault(rel_name, turn_id)
            applied_msg = f"Applied replacement relation schema for '{rel_name}'."

        elif phase == ElicitationState.ELICIT_INSTANCES:
            clean = new_input.strip()
            attrs: dict[str, Any] = {}
            core_line = clean
            if "[" in clean and clean.endswith("]"):
                b_idx = clean.find("[")
                attr_str = clean[b_idx:]
                core_line = clean[:b_idx].strip()
                try:
                    attrs = _parse_attributes(attr_str, 0)
                except Exception:
                    attrs = {}
            tokens = core_line.split()
            if len(tokens) == 3 and tokens[1] in (INSTANCE_OF, "instance_of"):
                inst, _, cls_name = tokens
                asrt = Assertion(
                    assertion_id=f"asrt_{turn_id}",
                    relation=Relation(inst, INSTANCE_OF, cls_name),
                    provenance=prov,
                    attributes=attrs,
                )
                target_turn.proposed_assertions = [asrt]
                target_turn.proposed_entities = {inst: attrs} if attrs else {}
                target_turn.user_response = new_input
                target_turn.confirmed = True
                if attrs:
                    self.model.add_entity(Entity(id=inst, attributes=dict(attrs)))
                self.model.add_assertion(
                    relation=asrt.relation,
                    provenance=asrt.provenance,
                    assertion_id=asrt.assertion_id,
                    attributes=asrt.attributes,
                )
                self._symbol_turn_map.setdefault(inst, turn_id)
                applied_msg = f"Applied replacement instance assertion: ({inst} instance_of {cls_name})."

        self.pending_reconfirmations = list(invalidated)
        base_msg = f"Amended {turn_id}: retracted {len(retracted)} assertions. {applied_msg}".strip()
        if self.pending_reconfirmations:
            next_t = self.pending_reconfirmations[0]
            self.current_prompt = (
                f"{base_msg} Re-confirmation required: confirm downstream turn "
                f"'{next_t.turn_id}' ('{next_t.user_response}')? (y/n)"
            )
            return self.current_prompt
        return base_msg

    def _finalize_elicitation(self) -> str:
        summary_lines = [
            f"Elicitation completed for scope: '{self.scope_description}'.",
            f"Entities created: {len(self.model.entities)}",
            f"Assertions landed: {len(self.model.assertions)}",
        ]

        if self.validation_hook:
            violations = self.validation_hook(self.model)
            if violations:
                summary_lines.append("Validation Warnings/Violations:")
                for v in violations:
                    summary_lines.append(f"  ! {v}")
            else:
                summary_lines.append("Model integrity checks: passed (0 violations).")

        self.current_prompt = "\n".join(summary_lines)
        return self.current_prompt

    def run_competency_queries(self) -> list[dict[str, Any]]:
        """Run recorded competency queries against the completed model."""
        session = DialogSession(model=self.model)
        results = []
        for q_str in self.competency_queries:
            doc = parse_dialog(f"dialog {self.model.uri}\n{q_str}")
            turn_results = [session.execute_statement(s) for s in doc.statements]
            results.append({
                "query": q_str,
                "passed": any(len(r.answers) > 0 for r in turn_results),
                "answers": [a.value for r in turn_results for a in r.answers],
            })
        return results
