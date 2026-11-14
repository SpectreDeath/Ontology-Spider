"""Mixed-initiative amendment helpers extracted from ElicitationManager."""

from __future__ import annotations

from typing import Any

from ontology_spider.dialog import _parse_attributes
from ontology_spider.model import (
    ACYCLIC,
    DISJOINT_WITH,
    DOMAIN,
    INSTANCE_OF,
    RANGE,
    SUBCLASS_OF,
    Assertion,
    Entity,
    Provenance,
    Relation,
)


def amend_decision_question(manager: Any, target_turn: Any, new_input: str) -> str:
    clean = new_input.strip()
    manager.scope_description = clean
    target_turn.user_response = clean
    target_turn.confirmed = True
    return f"Updated scope to '{manager.scope_description}'."


def amend_competency_question(manager: Any, target_turn: Any, new_input: str) -> str:
    clean = new_input.strip()
    target_turn.user_response = clean
    target_turn.confirmed = True
    if clean and clean not in manager.competency_queries:
        manager.competency_queries.append(clean)
    return f"Updated competency question to '{clean}'."


def amend_class_assertion(manager: Any, target_turn: Any, new_input: str, prov: Provenance) -> str:
    tokens = new_input.strip().split()
    if len(tokens) == 3 and tokens[1] == "subclass_of":
        sub, _, sup = tokens
        asrt = Assertion(
            assertion_id=f"asrt_{target_turn.turn_id}",
            relation=Relation(sub, SUBCLASS_OF, sup),
            provenance=prov,
        )
        target_turn.proposed_assertions = [asrt]
        target_turn.user_response = new_input
        target_turn.confirmed = True
        manager.model.add_assertion(relation=asrt.relation, provenance=asrt.provenance, assertion_id=asrt.assertion_id)
        manager._symbol_turn_map.setdefault(sub, target_turn.turn_id)
        manager._symbol_turn_map.setdefault(sup, target_turn.turn_id)
        return f"Applied replacement class hierarchy: ({sub} subclass_of {sup})."
    if len(tokens) == 3 and tokens[1] == "disjoint_with":
        c1, _, c2 = tokens
        asrt = Assertion(
            assertion_id=f"asrt_{target_turn.turn_id}",
            relation=Relation(c1, DISJOINT_WITH, c2),
            provenance=prov,
        )
        target_turn.proposed_assertions = [asrt]
        target_turn.user_response = new_input
        target_turn.confirmed = True
        manager.model.add_assertion(relation=asrt.relation, provenance=asrt.provenance, assertion_id=asrt.assertion_id)
        manager._symbol_turn_map.setdefault(c1, target_turn.turn_id)
        manager._symbol_turn_map.setdefault(c2, target_turn.turn_id)
        return f"Applied replacement disjointness: ({c1} disjoint_with {c2})."
    return f"Warning: Unrecognized class input '{new_input}'."


def amend_relation_assertion(manager: Any, target_turn: Any, new_input: str, prov: Provenance) -> str:
    tokens = new_input.strip().split()
    if not tokens:
        return "Warning: Empty relation input."
    rel_name = tokens[0]
    new_asrts = []
    for param in tokens[1:]:
        if param.startswith("domain="):
            d_val = param.split("=", 1)[1]
            new_asrts.append(Assertion(assertion_id=f"asrt_{target_turn.turn_id}_dom", relation=Relation(rel_name, DOMAIN, d_val), provenance=prov))
        elif param.startswith("range="):
            r_val = param.split("=", 1)[1]
            new_asrts.append(Assertion(assertion_id=f"asrt_{target_turn.turn_id}_rng", relation=Relation(rel_name, RANGE, r_val), provenance=prov))
        elif param.lower() == "acyclic=true":
            new_asrts.append(Assertion(assertion_id=f"asrt_{target_turn.turn_id}_acy", relation=Relation(rel_name, ACYCLIC, "true"), provenance=prov))
    target_turn.proposed_assertions = new_asrts
    target_turn.user_response = new_input
    target_turn.confirmed = True
    for a in new_asrts:
        manager.model.add_assertion(relation=a.relation, provenance=a.provenance, assertion_id=a.assertion_id)
    manager._symbol_turn_map.setdefault(rel_name, target_turn.turn_id)
    return f"Applied replacement relation schema for '{rel_name}'."


def amend_instance_assertion(manager: Any, target_turn: Any, new_input: str, prov: Provenance) -> str:
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
            assertion_id=f"asrt_{target_turn.turn_id}",
            relation=Relation(inst, INSTANCE_OF, cls_name),
            provenance=prov,
            attributes=attrs,
        )
        target_turn.proposed_assertions = [asrt]
        target_turn.proposed_entities = {inst: attrs} if attrs else {}
        target_turn.user_response = new_input
        target_turn.confirmed = True
        if attrs:
            manager.model.add_entity(Entity(id=inst, attributes=dict(attrs)))
        manager.model.add_assertion(
            relation=asrt.relation,
            provenance=asrt.provenance,
            assertion_id=asrt.assertion_id,
            attributes=asrt.attributes,
        )
        manager._symbol_turn_map.setdefault(inst, target_turn.turn_id)
        return f"Applied replacement instance assertion: ({inst} instance_of {cls_name})."
    if len(tokens) == 3:
        s, p, o = tokens
        asrt = Assertion(
            assertion_id=f"asrt_{target_turn.turn_id}",
            relation=Relation(s, p, o),
            provenance=prov,
            attributes=attrs,
        )
        target_turn.proposed_assertions = [asrt]
        target_turn.proposed_entities = {s: attrs} if attrs else {}
        target_turn.user_response = new_input
        target_turn.confirmed = True
        manager.model.add_assertion(
            relation=asrt.relation,
            provenance=asrt.provenance,
            assertion_id=asrt.assertion_id,
            attributes=asrt.attributes,
        )
        manager._symbol_turn_map.setdefault(s, target_turn.turn_id)
        return f"Applied replacement instance assertion: ({s} {p} {o})."
    return f"Warning: Unrecognized instance input '{new_input}'."
