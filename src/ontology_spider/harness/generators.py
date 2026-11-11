"""Synthetic ontology generators for benchmark topologies and property testing."""

from __future__ import annotations

import random

from ontology_spider.model import (
    ACYCLIC,
    SUBCLASS_OF,
    OntologyModel,
    Provenance,
    Relation,
)


def generate_chain(size: int, seed: int = 42) -> OntologyModel:
    """Generate linear subclass chain: c_0 <- c_1 <- ... <- c_{size-1}."""
    model = OntologyModel(uri=f"urn:test:gen:chain:{size}")
    prov = Provenance(source=f"gen:chain:seed={seed}")
    for i in range(size - 1):
        model.add_assertion(Relation(f"c_{i+1}", SUBCLASS_OF, f"c_{i}"), prov)
        model.upsert_entity(f"c_{i}", depth=i)
    model.upsert_entity(f"c_{size-1}", depth=size-1)
    return model


def generate_tree(size: int, branching: int = 2, seed: int = 42) -> OntologyModel:
    """Generate balanced subclass tree with given branching factor."""
    model = OntologyModel(uri=f"urn:test:gen:tree:{size}")
    prov = Provenance(source=f"gen:tree:seed={seed}")
    model.upsert_entity("node_0")
    for i in range(1, size):
        parent_id = f"node_{(i - 1) // branching}"
        child_id = f"node_{i}"
        model.add_assertion(Relation(child_id, SUBCLASS_OF, parent_id), prov)
        model.upsert_entity(child_id)
    return model


def generate_lattice(size: int, seed: int = 42) -> OntologyModel:
    """Generate diamond lattice with multiple reachability paths."""
    model = OntologyModel(uri=f"urn:test:gen:lattice:{size}")
    prov = Provenance(source=f"gen:lattice:seed={seed}")
    model.upsert_entity("top")
    prev_layer = ["top"]
    layer_idx = 1

    remaining = size
    while remaining > 0:
        layer_width = min(4, remaining)
        current_layer = [f"l_{layer_idx}_{j}" for j in range(layer_width)]
        for child in current_layer:
            model.upsert_entity(child)
            for parent in prev_layer:
                model.add_assertion(Relation(child, SUBCLASS_OF, parent), prov)
        remaining -= layer_width
        prev_layer = current_layer
        layer_idx += 1

    model.upsert_entity("bottom")
    for parent in prev_layer:
        model.add_assertion(Relation("bottom", SUBCLASS_OF, parent), prov)

    return model


def generate_random_dag(size: int, edge_prob: float = 0.2, seed: int = 42) -> OntologyModel:
    """Generate random DAG ensuring edges only point from higher to lower indices."""
    rng = random.Random(seed)
    model = OntologyModel(uri=f"urn:test:gen:dag:{size}")
    prov = Provenance(source=f"gen:dag:seed={seed}")

    for i in range(size):
        model.upsert_entity(f"n_{i}")

    for i in range(size):
        for j in range(i + 1, size):
            if rng.random() < edge_prob:
                model.add_assertion(Relation(f"n_{j}", SUBCLASS_OF, f"n_{i}"), prov)

    return model


def generate_cyclic(size: int, seed: int = 42) -> OntologyModel:
    """Generate cycle c_0 -> c_1 -> ... -> c_{size-1} -> c_0 on an acyclic relation."""
    model = OntologyModel(uri=f"urn:test:gen:cyclic:{size}")
    prov = Provenance(source=f"gen:cyclic:seed={seed}")
    model.add_assertion(Relation("subclass_of", ACYCLIC, "true"), prov)

    for i in range(size):
        nxt = (i + 1) % size
        model.add_assertion(Relation(f"c_{i}", SUBCLASS_OF, f"c_{nxt}"), prov)
        model.upsert_entity(f"c_{i}")

    return model
