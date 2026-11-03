"""Conversational traversal manager with DARPA Communicator-style frame stack and re-planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ontology_spider.dialog import DialogQuery, parse_dialog
from ontology_spider.dialog_runner import DialogSession, DialogTurnResult
from ontology_spider.model import OntologyModel
from ontology_spider.prolog.reasoner import PrologReasoner, ReasonerAnswer


@dataclass
class TraversalFrame:
    """An active conversational frame tracking focus entity, constraints, and query goal."""
    frame_id: str
    focus_entity: Optional[str] = None
    active_constraints: dict[str, str] = field(default_factory=dict)
    query_goal: Optional[str] = None
    last_answers: list[ReasonerAnswer] = field(default_factory=list)
    status: str = "active"  # "active", "completed", "aborted"


class TraversalDialogueManager:
    """Manages conversational traversal with frame stack, auditable paths, and constraint re-planning."""

    def __init__(
        self,
        model: OntologyModel,
        reasoner: Optional[PrologReasoner] = None,
    ) -> None:
        self.model = model
        self.reasoner = reasoner or PrologReasoner()
        self.session = DialogSession(model=self.model, reasoner=self.reasoner)
        self.frame_stack: list[TraversalFrame] = []
        self._frame_counter = 0

        # Create root frame
        self._push_frame(focus_entity=None, constraints={})

    def _push_frame(
        self, focus_entity: Optional[str], constraints: dict[str, str]
    ) -> TraversalFrame:
        self._frame_counter += 1
        frame = TraversalFrame(
            frame_id=f"frame_{self._frame_counter}",
            focus_entity=focus_entity,
            active_constraints=dict(constraints),
        )
        self.frame_stack.append(frame)
        return frame

    @property
    def current_frame(self) -> TraversalFrame:
        return self.frame_stack[-1]

    def where_am_i(self) -> str:
        """Inspect current conversational position across frame stack."""
        lines = [f"Traversal Stack ({len(self.frame_stack)} frames active):"]
        for idx, frame in enumerate(self.frame_stack, start=1):
            focus = frame.focus_entity or "none"
            constraints_str = ", ".join(f"{k}={v}" for k, v in frame.active_constraints.items()) or "none"
            goal = frame.query_goal or "none"
            lines.append(
                f"  [{idx}] {frame.frame_id}: focus='{focus}', constraints='{constraints_str}', goal='{goal}' ({frame.status})"
            )
        return "\n".join(lines)

    def set_focus(self, entity_id: str, constraints: Optional[dict[str, str]] = None) -> str:
        """Push a new subdialogue frame focusing on a specific entity."""
        active_constraints = dict(self.current_frame.active_constraints)
        if constraints:
            active_constraints.update(constraints)
        frame = self._push_frame(focus_entity=entity_id, constraints=active_constraints)
        return f"Focused on entity '{entity_id}' in {frame.frame_id}."

    def change_constraint(self, key: str, value: str) -> str:
        """DARPA Communicator re-planning: change constraint, aborting invalidated subframes."""
        current = self.current_frame
        old_val = current.active_constraints.get(key)
        if old_val == value:
            return f"Constraint '{key}' already set to '{value}'."

        aborted_frames: list[str] = []
        # If current subframe was focused on an entity that violates the new constraint, pop/abort it
        while len(self.frame_stack) > 1:
            top = self.frame_stack[-1]
            focus = top.focus_entity
            if focus:
                ent = self.model.get_entity(focus)
                if ent and str(ent.attributes.get(key)) != str(value):
                    top.status = "aborted"
                    aborted_frames.append(top.frame_id)
                    self.frame_stack.pop()
                    continue
            break

        # Apply constraint to top frame
        self.current_frame.active_constraints[key] = value

        msg = f"Updated constraint {key}='{value}' in {self.current_frame.frame_id}."
        if aborted_frames:
            msg += f" Aborted conflicting subdialogue frames: {', '.join(aborted_frames)}."
        return msg

    def query(self, query_text: str) -> DialogTurnResult:
        """Execute a query turn within the active conversational frame."""
        clean = query_text.strip()
        doc = parse_dialog(f"dialog {self.model.uri}\n{clean}")
        if not doc.statements:
            raise ValueError(f"No valid query parsed from: {query_text}")

        stmt = doc.statements[0]
        if isinstance(stmt, DialogQuery):
            # If query lacks subject but frame has focus entity, inherit it
            if not stmt.subject and self.current_frame.focus_entity:
                stmt = DialogQuery(
                    kind=stmt.kind,
                    subject=self.current_frame.focus_entity,
                    predicate=stmt.predicate,
                    object=stmt.object,
                    filter_key=stmt.filter_key,
                    filter_val=stmt.filter_val,
                    raw_text=stmt.raw_text,
                    line_num=stmt.line_num,
                )

        result = self.session.execute_statement(stmt)
        self.current_frame.query_goal = clean
        self.current_frame.last_answers = list(result.answers)
        return result

    def explain(self) -> str:
        """Explain the most recent answer in the active frame."""
        res = self.session.execute_statement(DialogQuery(kind="explain"))
        return res.summary_text
