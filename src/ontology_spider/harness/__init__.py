"""Harness package initialization."""

from ontology_spider.harness.bench import run_benchmarks
from ontology_spider.harness.generators import (
    generate_chain,
    generate_cyclic,
    generate_lattice,
    generate_random_dag,
    generate_tree,
)
from ontology_spider.harness.properties import (
    check_ancestor_superset_of_parents,
    check_cycle_triggers_violation,
    check_dialog_roundtrip_identity,
    check_json_roundtrip_identity,
)
from ontology_spider.harness.runner import HarnessReport, HarnessRunner

__all__ = [
    "HarnessRunner",
    "HarnessReport",
    "run_benchmarks",
    "generate_chain",
    "generate_tree",
    "generate_lattice",
    "generate_random_dag",
    "generate_cyclic",
    "check_json_roundtrip_identity",
    "check_dialog_roundtrip_identity",
    "check_ancestor_superset_of_parents",
    "check_cycle_triggers_violation",
]
