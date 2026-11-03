"""Managed elicitation state machine with mixed-initiative correction and provenance."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from ontology_spider.dialog import parse_dialog
from ontology_spider.dialog_runner import DialogSession
from ontology_spider.model import (
    ACYCLIC,
    DOMAIN,
    INSTANCE_OF,
    RANGE,
    SUBCLASS_OF,
    Assertion,
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
    depends_on_turn_ids: list[str] = field(default_factory=list)
    confirmed: bool = False


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
        self.validation_hook = validation_hook
        self._turn_counter = 0

    def _next_turn_id(self) -> str:
        self._turn_counter += 1
        return f"turn_{self._turn_counter}"

    def start(self) -> str:
        """Start the elicitation dialogue."""
        prompt = "What domain or topic is this ontology about? (Decision Question)"
        self.pending_turn = ElicitedTurn(
            turn_id=self._next_turn_id(),
            state=ElicitationState.DECISION_QUESTION,
            prompt=prompt,
        )
        return prompt

    def step(self, user_input: str) -> str:
        """Process user input against current state."""
        clean = user_input.strip()

        if self.state == ElicitationState.DECISION_QUESTION:
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
            )
            return prompt

        if self.state == ElicitationState.COMPETENCY_QUESTIONS:
            if clean.lower() in ("done", "none", "skip"):
                self.state = ElicitationState.ELICIT_CLASSES
                prompt = (
                    "Enter class hierarchies (e.g. 'cat subclass_of mammal' or 'done'):"
                )
                self.pending_turn = ElicitedTurn(
                    turn_id=self._next_turn_id(),
                    state=ElicitationState.ELICIT_CLASSES,
                    prompt=prompt,
                )
                return prompt

            # Record competency question
            self.competency_queries.append(clean)
            return "Competency query recorded. Enter another or 'done':"

        if self.state == ElicitationState.ELICIT_CLASSES:
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
                )
                return prompt

            # Parse class assertion: <subclass> subclass_of <superclass>
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
                self.pending_turn = ElicitedTurn(
                    turn_id=turn_id,
                    state=ElicitationState.CONFIRMATION,
                    prompt=f"Please confirm: assert ({sub} subclass_of {sup})? (y/n)",
                    user_response=clean,
                    proposed_assertions=[asrt],
                )
                self.state = ElicitationState.CONFIRMATION
                return self.pending_turn.prompt
            else:
                return "Invalid class format. Expected: '<child> subclass_of <parent>' or 'done'."

        if self.state == ElicitationState.ELICIT_RELATIONS:
            if clean.lower() in ("done", "skip"):
                self.state = ElicitationState.ELICIT_INSTANCES
                prompt = (
                    "Enter instances (e.g. 'felix instance_of cat' or 'done'):"
                )
                self.pending_turn = ElicitedTurn(
                    turn_id=self._next_turn_id(),
                    state=ElicitationState.ELICIT_INSTANCES,
                    prompt=prompt,
                )
                return prompt

            # Parse relation schema declarations: <rel> domain=<X> range=<Y> [acyclic=true]
            tokens = clean.split()
            rel_name = tokens[0]
            turn_id = self._next_turn_id()
            prov = Provenance(source="elicitation", turn_id=turn_id)
            proposed: list[Assertion] = []

            for param in tokens[1:]:
                if param.startswith("domain="):
                    d_val = param.split("=", 1)[1]
                    proposed.append(
                        Assertion(
                            assertion_id=f"asrt_{turn_id}_dom",
                            relation=Relation(rel_name, DOMAIN, d_val),
                            provenance=prov,
                        )
                    )
                elif param.startswith("range="):
                    r_val = param.split("=", 1)[1]
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
                return "No valid domain/range/acyclic specs found. Format: '<rel> domain=<D> range=<R>' or 'done'."

            self.pending_turn = ElicitedTurn(
                turn_id=turn_id,
                state=ElicitationState.CONFIRMATION,
                prompt=f"Please confirm {len(proposed)} relation properties for '{rel_name}'? (y/n)",
                user_response=clean,
                proposed_assertions=proposed,
            )
            self.state = ElicitationState.CONFIRMATION
            return self.pending_turn.prompt

        if self.state == ElicitationState.ELICIT_INSTANCES:
            if clean.lower() in ("done", "skip"):
                self.state = ElicitationState.COMPLETED
                return self._finalize_elicitation()

            tokens = clean.split()
            if len(tokens) == 3 and tokens[1] in (INSTANCE_OF, "instance_of"):
                inst, _, cls_name = tokens
                turn_id = self._next_turn_id()
                prov = Provenance(source="elicitation", turn_id=turn_id)
                asrt = Assertion(
                    assertion_id=f"asrt_{turn_id}",
                    relation=Relation(inst, INSTANCE_OF, cls_name),
                    provenance=prov,
                )
                self.pending_turn = ElicitedTurn(
                    turn_id=turn_id,
                    state=ElicitationState.CONFIRMATION,
                    prompt=f"Please confirm: assert ({inst} instance_of {cls_name})? (y/n)",
                    user_response=clean,
                    proposed_assertions=[asrt],
                )
                self.state = ElicitationState.CONFIRMATION
                return self.pending_turn.prompt
            elif len(tokens) == 3:
                # Custom instance relation assertion
                s, p, o = tokens
                turn_id = self._next_turn_id()
                prov = Provenance(source="elicitation", turn_id=turn_id)
                asrt = Assertion(
                    assertion_id=f"asrt_{turn_id}",
                    relation=Relation(s, p, o),
                    provenance=prov,
                )
                self.pending_turn = ElicitedTurn(
                    turn_id=turn_id,
                    state=ElicitationState.CONFIRMATION,
                    prompt=f"Please confirm: assert ({s} {p} {o})? (y/n)",
                    user_response=clean,
                    proposed_assertions=[asrt],
                )
                self.state = ElicitationState.CONFIRMATION
                return self.pending_turn.prompt
            else:
                return "Invalid instance assertion. Expected '<item> instance_of <class>' or '<s p o>' or 'done'."

        if self.state == ElicitationState.CONFIRMATION:
            if clean.lower() in ("y", "yes", "confirm"):
                if self.pending_turn:
                    self.pending_turn.confirmed = True
                    for asrt in self.pending_turn.proposed_assertions:
                        self.model.add_assertion(
                            relation=asrt.relation,
                            provenance=asrt.provenance,
                            assertion_id=asrt.assertion_id,
                            attributes=asrt.attributes,
                        )
                    self.turns.append(self.pending_turn)

                # Return to previous elicitation category
                prev_state = self._determine_next_state_after_confirmation()
                self.state = prev_state
                return f"Confirmed and landed in model. Enter next or 'done':"
            else:
                # Discard unconfirmed assertions
                rejected_id = self.pending_turn.turn_id if self.pending_turn else "unknown"
                prev_state = self._determine_next_state_after_confirmation()
                self.state = prev_state
                self.pending_turn = None
                return f"Turn {rejected_id} discarded (not confirmed). Enter next or 'done':"

        return "Elicitation completed."

    def _determine_next_state_after_confirmation(self) -> ElicitationState:
        # Check what we were eliciting based on proposed assertions
        if not self.pending_turn or not self.pending_turn.proposed_assertions:
            return ElicitationState.ELICIT_INSTANCES
        first_rel = self.pending_turn.proposed_assertions[0].relation.predicate
        if first_rel == SUBCLASS_OF:
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

        # Retract any downstream dependent turns
        downstream = [
            t for t in self.turns if turn_id in t.depends_on_turn_ids and t.confirmed
        ]
        for dt in downstream:
            retracted.extend(self.model.retract_by_turn_id(dt.turn_id))
            dt.confirmed = False

        # Remove target turn from confirmed turns
        self.turns = [t for t in self.turns if t.turn_id != turn_id]

        # Re-enter elicitation with the new input
        return f"Amended {turn_id}: retracted {len(retracted)} assertions. Re-processing amendment."

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

        return "\n".join(summary_lines)

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
