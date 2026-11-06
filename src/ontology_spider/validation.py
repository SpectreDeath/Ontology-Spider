"""Ontology validation, integrity constraints, and assumption verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ontology_spider.model import (
    ACYCLIC,
    BUILTIN_SCHEMA_PREDICATES,
    DISJOINT_WITH,
    DOMAIN,
    INSTANCE_OF,
    RANGE,
    SUBCLASS_OF,
    Assertion,
    OntologyModel,
)


@dataclass
class Violation:
    """A detected integrity violation or failed assumption."""
    check_type: str
    message: str
    offending_assertion_ids: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        asrt_info = f" [assertions: {', '.join(self.offending_assertion_ids)}]" if self.offending_assertion_ids else ""
        return f"[{self.check_type}] {self.message}{asrt_info}"


@dataclass
class AssumptionDefinition:
    """Data-defined assumption check definition."""
    name: str
    description: str
    check_fn: Callable[[OntologyModel], list[Violation]]


class OntologyValidator:
    """Verifies domain/range, disjointness, acyclicity, and configurable assumptions."""

    def __init__(
        self, custom_assumptions: Optional[list[AssumptionDefinition]] = None
    ) -> None:
        self.assumptions: list[AssumptionDefinition] = [
            AssumptionDefinition(
                name="no_orphan_instances",
                description="Every instance entity must belong to a declared class.",
                check_fn=self._check_no_orphan_instances,
            ),
            AssumptionDefinition(
                name="declared_domain_and_range",
                description="Every domain relation should declare its domain and range.",
                check_fn=self._check_declared_domain_and_range,
            ),
        ]
        if custom_assumptions:
            self.assumptions.extend(custom_assumptions)

    def validate(self, model: OntologyModel) -> list[Violation]:
        """Run all constraint checks and assumption verifications against a model."""
        violations: list[Violation] = []

        # 1. Transitive class hierarchy cache for domain/range and disjointness checks
        subclass_parents: dict[str, set[str]] = {}
        for asrt in model.query(predicate=SUBCLASS_OF):
            subclass_parents.setdefault(asrt.relation.subject, set()).add(
                asrt.relation.object
            )

        superclass_cache: dict[str, set[str]] = {}

        def get_all_superclasses(c: str, visited: Optional[set[str]] = None) -> set[str]:
            if c in superclass_cache:
                return superclass_cache[c]
            visited = visited or set()
            supers = set()
            for parent in subclass_parents.get(c, set()):
                if parent not in visited:
                    visited.add(parent)
                    supers.add(parent)
                    supers.update(get_all_superclasses(parent, visited))
            superclass_cache[c] = supers
            return supers

        types_cache: dict[str, set[str]] = {}
        class_members: dict[str, set[str]] = {}

        def get_types(entity_id: str) -> set[str]:
            if entity_id in types_cache:
                return types_cache[entity_id]
            types = set()
            for asrt in model.query(subject=entity_id, predicate=INSTANCE_OF):
                cls_name = asrt.relation.object
                types.add(cls_name)
                types.update(get_all_superclasses(cls_name))
            if entity_id in subclass_parents:
                types.add(entity_id)
                types.update(get_all_superclasses(entity_id))
            types_cache[entity_id] = types
            for t in types:
                class_members.setdefault(t, set()).add(entity_id)
            return types

        for ent_id in model.entities:
            get_types(ent_id)

        # 2. Domain and Range constraint checks
        domain_specs: dict[str, list[Assertion]] = {}
        range_specs: dict[str, list[Assertion]] = {}
        for asrt in model.query(predicate=DOMAIN):
            domain_specs.setdefault(asrt.relation.subject, []).append(asrt)
        for asrt in model.query(predicate=RANGE):
            range_specs.setdefault(asrt.relation.subject, []).append(asrt)

        for asrt in model.assertions.values():
            pred = asrt.relation.predicate
            if pred in BUILTIN_SCHEMA_PREDICATES:
                continue

            # Domain check
            if pred in domain_specs:
                subj_types = get_types(asrt.relation.subject)
                for dom_asrt in domain_specs[pred]:
                    expected_dom = dom_asrt.relation.object
                    if expected_dom not in subj_types:
                        violations.append(
                            Violation(
                                check_type="domain_violation",
                                message=(
                                    f"Entity '{asrt.relation.subject}' uses relation '{pred}' "
                                    f"but is not of declared domain '{expected_dom}'"
                                ),
                                offending_assertion_ids=[
                                    asrt.assertion_id,
                                    dom_asrt.assertion_id,
                                ],
                            )
                        )

            # Range check
            if pred in range_specs:
                obj_types = get_types(asrt.relation.object)
                for rng_asrt in range_specs[pred]:
                    expected_rng = rng_asrt.relation.object
                    if expected_rng not in obj_types:
                        violations.append(
                            Violation(
                                check_type="range_violation",
                                message=(
                                    f"Entity '{asrt.relation.object}' is target of relation '{pred}' "
                                    f"but is not of declared range '{expected_rng}'"
                                ),
                                offending_assertion_ids=[
                                    asrt.assertion_id,
                                    rng_asrt.assertion_id,
                                ],
                            )
                        )

        # 3. Disjointness check
        def get_assertions_to_ancestor(start: str, target: str) -> list[str]:
            if start == target:
                return []
            queue: list[tuple[str, list[str]]] = [(start, [])]
            visited: set[str] = {start}
            while queue:
                curr, path_aids = queue.pop(0)
                if curr == target:
                    return path_aids
                for a in model.query(subject=curr):
                    if a.relation.predicate in (INSTANCE_OF, SUBCLASS_OF):
                        nxt = a.relation.object
                        if nxt not in visited:
                            visited.add(nxt)
                            queue.append((nxt, path_aids + [a.assertion_id]))
            return []

        for asrt in model.query(predicate=DISJOINT_WITH):
            c1 = asrt.relation.subject
            c2 = asrt.relation.object
            overlapping_entities = class_members.get(c1, set()) & class_members.get(c2, set())
            for ent_id in sorted(overlapping_entities):
                path1_aids = get_assertions_to_ancestor(ent_id, c1)
                path2_aids = get_assertions_to_ancestor(ent_id, c2)
                offending = [asrt.assertion_id]
                for aid in path1_aids + path2_aids:
                    if aid not in offending:
                        offending.append(aid)
                if len(offending) == 1:
                    for a in model.query(subject=ent_id, predicate=INSTANCE_OF):
                        if a.assertion_id not in offending:
                            offending.append(a.assertion_id)

                violations.append(
                    Violation(
                        check_type="disjointness_violation",
                        message=(
                            f"Entity '{ent_id}' is asserted as both '{c1}' and '{c2}', "
                            f"which are declared disjoint."
                        ),
                        offending_assertion_ids=offending,
                    )
                )

        # 4. Cycle detection on relations declared acyclic (and subclass_of intrinsically)
        acyclic_preds = {SUBCLASS_OF} | {
            a.relation.subject
            for a in model.query(predicate=ACYCLIC)
            if a.relation.object.lower() in ("true", "yes", "1")
        }

        for pred in acyclic_preds:
            # Build graph for pred: node -> list of (target, assertion_id)
            graph: dict[str, list[tuple[str, str]]] = {}
            for asrt in model.query(predicate=pred):
                graph.setdefault(asrt.relation.subject, []).append(
                    (asrt.relation.object, asrt.assertion_id)
                )

            # Tarjan's Strongly Connected Components (SCC) algorithm O(V + E)
            index = 0
            indices: dict[str, int] = {}
            lowlinks: dict[str, int] = {}
            on_stack: set[str] = set()
            stack: list[str] = []
            sccs: list[list[str]] = []

            all_nodes = set(graph.keys())
            for targets in graph.values():
                for tgt, _ in targets:
                    all_nodes.add(tgt)

            def strongconnect(v: str) -> None:
                nonlocal index
                indices[v] = index
                lowlinks[v] = index
                index += 1
                stack.append(v)
                on_stack.add(v)

                for w, _ in graph.get(v, []):
                    if w not in indices:
                        strongconnect(w)
                        lowlinks[v] = min(lowlinks[v], lowlinks[w])
                    elif w in on_stack:
                        lowlinks[v] = min(lowlinks[v], indices[w])

                if lowlinks[v] == indices[v]:
                    scc = []
                    while True:
                        w = stack.pop()
                        on_stack.remove(w)
                        scc.append(w)
                        if w == v:
                            break
                    if len(scc) > 1 or any(tgt == v for tgt, _ in graph.get(v, [])):
                        sccs.append(scc)

            for node in all_nodes:
                if node not in indices:
                    strongconnect(node)

            # For each cyclic SCC, extract a witness cycle
            for scc in sccs:
                scc_set = set(scc)
                # Find a simple cycle inside scc
                start_node = scc[0]
                parent_edge: dict[str, tuple[str, str]] = {}  # node -> (parent, asrt_id)
                queue = [start_node]
                cycle_edges: list[str] = []
                found = False

                while queue and not found:
                    curr = queue.pop(0)
                    for nxt, aid in graph.get(curr, []):
                        if nxt not in scc_set:
                            continue
                        if nxt == start_node and curr != start_node:
                            # Reconstruct cycle
                            cycle_edges = [aid]
                            trace = curr
                            while trace != start_node:
                                prev_node, prev_aid = parent_edge[trace]
                                cycle_edges.append(prev_aid)
                                trace = prev_node
                            cycle_edges.reverse()
                            found = True
                            break
                        elif nxt not in parent_edge and nxt != start_node:
                            parent_edge[nxt] = (curr, aid)
                            queue.append(nxt)

                # Self-loop case
                if not found:
                    for tgt, aid in graph.get(start_node, []):
                        if tgt == start_node:
                            cycle_edges = [aid]
                            break

                violations.append(
                    Violation(
                        check_type="cycle_violation",
                        message=f"Directed cycle detected in relation '{pred}' declared acyclic.",
                        offending_assertion_ids=cycle_edges,
                    )
                )


        # 5. Assumption checks
        for assumption in self.assumptions:
            violations.extend(assumption.check_fn(model))

        return violations

    def _check_no_orphan_instances(self, model: OntologyModel) -> list[Violation]:
        violations: list[Violation] = []
        # Find all entities that are not classes and have no instance_of
        classes: set[str] = set()
        for asrt in model.query(predicate=SUBCLASS_OF):
            classes.add(asrt.relation.subject)
            classes.add(asrt.relation.object)
        for asrt in model.query(predicate=INSTANCE_OF):
            classes.add(asrt.relation.object)

        schema_entities: set[str] = set()
        for asrt in model.assertions.values():
            if asrt.relation.predicate in (DOMAIN, RANGE, ACYCLIC, DISJOINT_WITH):
                schema_entities.add(asrt.relation.subject)
                schema_entities.add(asrt.relation.object)

        for ent_id in model.entities:
            if ent_id in classes or ent_id in schema_entities:
                continue
            inst_asrts = model.query(subject=ent_id, predicate=INSTANCE_OF)
            if not inst_asrts:
                # Entity is an orphan instance
                violations.append(
                    Violation(
                        check_type="assumption_violation",
                        message=f"Orphan instance entity '{ent_id}' has no declared class membership.",
                    )
                )
        return violations

    def _check_declared_domain_and_range(self, model: OntologyModel) -> list[Violation]:
        violations: list[Violation] = []
        domain_preds = {a.relation.subject for a in model.query(predicate=DOMAIN)}
        range_preds = {a.relation.subject for a in model.query(predicate=RANGE)}

        all_preds = {
            asrt.relation.predicate
            for asrt in model.assertions.values()
            if asrt.relation.predicate not in BUILTIN_SCHEMA_PREDICATES
        }

        for pred in all_preds:
            missing = []
            if pred not in domain_preds:
                missing.append("domain")
            if pred not in range_preds:
                missing.append("range")
            if missing:
                violations.append(
                    Violation(
                        check_type="assumption_violation",
                        message=f"Relation '{pred}' is missing declared {', '.join(missing)}.",
                    )
                )
        return violations


def validate_model_hook(model: OntologyModel) -> list[str]:
    """Helper hook providing human-readable validation summaries for ElicitationManager."""
    validator = OntologyValidator()
    violations = validator.validate(model)
    return [v.summary() for v in violations]
