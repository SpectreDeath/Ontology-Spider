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

        def get_all_superclasses(c: str, visited: Optional[set[str]] = None) -> set[str]:
            visited = visited or set()
            supers = set()
            for parent in subclass_parents.get(c, set()):
                if parent not in visited:
                    visited.add(parent)
                    supers.add(parent)
                    supers.update(get_all_superclasses(parent, visited))
            return supers

        def get_types(entity_id: str) -> set[str]:
            types = set()
            for asrt in model.query(subject=entity_id, predicate=INSTANCE_OF):
                cls_name = asrt.relation.object
                types.add(cls_name)
                types.update(get_all_superclasses(cls_name))
            if entity_id in subclass_parents:
                types.add(entity_id)
                types.update(get_all_superclasses(entity_id))
            return types

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
        for asrt in model.query(predicate=DISJOINT_WITH):
            c1 = asrt.relation.subject
            c2 = asrt.relation.object
            for ent_id in model.entities:
                ent_types = get_types(ent_id)
                if c1 in ent_types and c2 in ent_types:
                    # Find instance assertions for ent_id
                    inst_ids = [
                        a.assertion_id
                        for a in model.query(subject=ent_id, predicate=INSTANCE_OF)
                    ]
                    violations.append(
                        Violation(
                            check_type="disjointness_violation",
                            message=(
                                f"Entity '{ent_id}' is asserted as both '{c1}' and '{c2}', "
                                f"which are declared disjoint."
                            ),
                            offending_assertion_ids=[asrt.assertion_id] + inst_ids,
                        )
                    )

        # 4. Cycle detection on relations declared acyclic
        acyclic_preds = {
            a.relation.subject
            for a in model.query(predicate=ACYCLIC)
            if a.relation.object.lower() in ("true", "yes", "1")
        }

        for pred in acyclic_preds:
            # Build graph for pred
            graph: dict[str, list[tuple[str, str]]] = {}
            for asrt in model.query(predicate=pred):
                graph.setdefault(asrt.relation.subject, []).append(
                    (asrt.relation.object, asrt.assertion_id)
                )

            # Detect cycle using DFS
            visited_global: set[str] = set()

            def dfs(node: str, path: list[str], edges: list[str]) -> Optional[list[str]]:
                if node in path:
                    cycle_start = path.index(node)
                    return edges[cycle_start:]
                if node in visited_global:
                    return None

                path.append(node)
                visited_global.add(node)

                for next_node, aid in graph.get(node, []):
                    cycle_edges = dfs(next_node, list(path), edges + [aid])
                    if cycle_edges:
                        return cycle_edges
                return None

            for start_node in graph:
                cycle_aids = dfs(start_node, [], [])
                if cycle_aids:
                    violations.append(
                        Violation(
                            check_type="cycle_violation",
                            message=f"Directed cycle detected in relation '{pred}' declared acyclic.",
                            offending_assertion_ids=cycle_aids,
                        )
                    )
                    break

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

        for ent_id in model.entities:
            if ent_id in classes:
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
