"""Property-based verification invariants for Ontology-Spider models."""

from __future__ import annotations

import json

from ontology_spider.engine import Engine
from ontology_spider.export import to_dialog, to_json
from ontology_spider.model import (
    INSTANCE_OF,
    SUBCLASS_OF,
    OntologyModel,
)
from ontology_spider.reasoning.base import QuerySpec
from ontology_spider.reasoning.python_backend import PythonReasoner
from ontology_spider.seam import DialogModelSource
from ontology_spider.traversal import TraversalDialogueManager
from ontology_spider.validation import OntologyValidator


def check_json_roundtrip_identity(model: OntologyModel) -> bool:
    """Invariant: to_json -> from_dict preserves model entities and assertions exactly."""
    raw = to_json(model)
    data = json.loads(raw)
    restored = OntologyModel.from_dict(data)
    if set(model.entities.keys()) != set(restored.entities.keys()):
        return False
    if set(model.assertions.keys()) != set(restored.assertions.keys()):
        return False
    return True


def check_dialog_roundtrip_identity(model: OntologyModel) -> bool:
    """Invariant: to_dialog -> DialogModelSource re-parses to equal entities and assertions (exact lossless roundtrip)."""
    text = to_dialog(model)
    restored = DialogModelSource(text).load()
    if model.uri != restored.uri:
        return False
    if set(model.entities.keys()) != set(restored.entities.keys()):
        return False
    for eid, ent in model.entities.items():
        rent = restored.entities.get(eid)
        if rent is None:
            return False
        if (ent.name or "") != (rent.name or ""):
            return False
        if dict(ent.attributes) != dict(rent.attributes):
            return False
        for k, v in ent.attributes.items():
            rv = rent.attributes.get(k)
            if type(v) is not type(rv) or v != rv:
                return False

    if len(model.assertions) != len(restored.assertions):
        return False
    for aid, a in model.assertions.items():
        ra = restored.assertions.get(aid)
        if ra is None:
            matching = [
                x for x in restored.assertions.values()
                if x.relation.subject == a.relation.subject
                and x.relation.predicate == a.relation.predicate
                and x.relation.object == a.relation.object
            ]
            if not matching:
                return False
            ra = matching[0]

        if (
            ra.relation.subject != a.relation.subject
            or ra.relation.predicate != a.relation.predicate
            or ra.relation.object != a.relation.object
        ):
            return False
        if a.assertion_id and ra.assertion_id != a.assertion_id:
            return False
        if a.provenance.source and ra.provenance.source != a.provenance.source:
            return False
        if a.provenance.turn_id and ra.provenance.turn_id != a.provenance.turn_id:
            return False
        if a.provenance.timestamp and ra.provenance.timestamp != a.provenance.timestamp:
            return False
        if a.provenance.parent_turn_ids != ra.provenance.parent_turn_ids:
            return False
        if dict(a.attributes) != dict(ra.attributes):
            return False
        for k, v in a.attributes.items():
            rv = ra.attributes.get(k)
            if type(v) is not type(rv) or v != rv:
                return False

    return True


def check_ancestor_superset_of_parents(model: OntologyModel, target: str, ancestors: list[str]) -> bool:
    """Invariant: transitive ancestors are always a superset of direct parents."""
    parents = {
        a.relation.object
        for a in model.query(subject=target)
        if a.relation.predicate in (SUBCLASS_OF, INSTANCE_OF)
    }
    return parents.issubset(set(ancestors))


def check_cycle_triggers_violation(model: OntologyModel) -> bool:
    """Invariant: model with a cycle triggers at least one cycle_violation in validator."""
    validator = OntologyValidator()
    violations = validator.validate(model)
    return any(v.check_type == "cycle_violation" for v in violations)


def verify_transitivity_monotonicity(model: OntologyModel, predicate: str = SUBCLASS_OF) -> bool:
    """Invariant: for every edge (u, v), ancestors(v) is a subset of ancestors(u)."""
    edges = [a for a in model.assertions.values() if a.relation.predicate == predicate]
    reasoner = PythonReasoner()
    for edge in edges:
        u = edge.relation.subject
        v = edge.relation.object
        spec_u = QuerySpec(kind="ancestors", subject=u)
        spec_v = QuerySpec(kind="ancestors", subject=v)
        res_u = reasoner.query(model, spec_u)
        res_v = reasoner.query(model, spec_v)
        anc_u = {str(ans.value) for ans in res_u.answers}
        anc_v = {str(ans.value) for ans in res_v.answers}
        if v not in anc_u:
            return False
        if not anc_v.issubset(anc_u):
            return False
    return True


def verify_roundtrip_dialog(model: OntologyModel) -> bool:
    return check_dialog_roundtrip_identity(model)


def verify_roundtrip_json(model: OntologyModel) -> bool:
    return check_json_roundtrip_identity(model)


def verify_validation_cycle_detection(model: OntologyModel, expect_cycle: bool) -> bool:
    has_cycle = check_cycle_triggers_violation(model)
    return has_cycle == expect_cycle


def verify_frame_scoping_invariant(model: OntologyModel) -> bool:
    """Invariant: pushing a subdialogue frame isolates or constrains results monotonically."""
    manager = TraversalDialogueManager(model)
    entities = list(model.entities.keys())
    if not entities:
        return True
    target = entities[0]
    base_res = manager.query(f"query what is {target}?")

    manager.set_focus(entity_id=target)
    scoped_res = manager.query(f"query what is {target}?")
    return len(scoped_res.answers) <= len(base_res.answers)


def verify_path_query_consistency(model: OntologyModel) -> bool:
    """Invariant: every direct taxonomic edge has a consistent shortest path query answer."""
    tax_edges = [
        a for a in model.assertions.values()
        if a.relation.predicate in (SUBCLASS_OF, INSTANCE_OF)
    ]
    if not tax_edges:
        return True
    engine = Engine()
    edge = tax_edges[0]
    u, v = edge.relation.subject, edge.relation.object
    res = engine.query(model, f"query path from {u} to {v}")
    if not res.answers:
        return False
    path_str = str(res.answers[0]["value"])
    return path_str.startswith(u) and path_str.endswith(v)


def verify_negation_query_consistency(model: OntologyModel) -> bool:
    """Invariant: absent triples return 'true' under query not and present triples return 'false'."""
    engine = Engine()
    absent = engine.query(model, "query not __nonexistent_entity__ subclass_of __nonexistent_target__")
    if not absent.answers or str(absent.answers[0]["value"]) != "true":
        return False
    first_asrt = next(iter(model.assertions.values()), None)
    if first_asrt is None:
        return True
    rel = first_asrt.relation
    present = engine.query(model, f"query not {rel.subject} {rel.predicate} {rel.object}")
    return bool(present.answers) and str(present.answers[0]["value"]) == "false"


def verify_count_query_consistency(model: OntologyModel) -> bool:
    """Invariant: query count matches exact answer cardinality of the wrapped inner query."""
    first_ent = next(iter(model.entities.keys()), None)
    if first_ent is None:
        return True
    engine = Engine()
    inner = engine.query(model, f"query what is {first_ent}?")
    counted = engine.query(model, f"query count what is {first_ent}?")
    if not counted.answers:
        return False
    return int(counted.answers[0]["value"]) == len(inner.answers)
