"""Benchmarking runner measuring p50/p95 query and validation latency."""

from __future__ import annotations

import time
from typing import Any

from ontology_spider.engine import Session
from ontology_spider.harness.generators import generate_chain, generate_lattice, generate_tree
from ontology_spider.model import OntologyModel
from ontology_spider.validation import OntologyValidator


def run_benchmarks() -> dict[str, Any]:
    """Execute standard benchmarks and return latency measurements in milliseconds."""
    results: dict[str, Any] = {}

    # 1. Chain ancestry traversal (50 nodes)
    chain = generate_chain(50)
    session = Session(model=chain)
    latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        session.execute("query ancestors of c_49")
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    results["chain_50_ancestors_p50_ms"] = round(latencies[len(latencies) // 2], 2)

    # 2. Tree recommendation traversal (100 nodes)
    tree = generate_tree(100)
    session_tree = Session(model=tree)
    latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        session_tree.execute("query recommend node_0")
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    results["tree_100_recommend_p50_ms"] = round(latencies[len(latencies) // 2], 2)

    # 3. Lattice validation (50 nodes)
    lattice = generate_lattice(50)
    validator = OntologyValidator()
    latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        validator.validate(lattice)
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    results["lattice_50_validate_p50_ms"] = round(latencies[len(latencies) // 2], 2)

    return results
