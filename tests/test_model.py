import unittest
from ontology_spider.model import (
    Entity,
    Relation,
    Provenance,
    Assertion,
    OntologyModel,
    INSTANCE_OF,
    SUBCLASS_OF,
    DOMAIN,
    RANGE,
    DISJOINT_WITH,
    ACYCLIC,
    BUILTIN_SCHEMA_PREDICATES,
)


class TestModel(unittest.TestCase):
    def test_canonical_schema_vocabulary(self):
        self.assertIn(INSTANCE_OF, BUILTIN_SCHEMA_PREDICATES)
        self.assertIn(SUBCLASS_OF, BUILTIN_SCHEMA_PREDICATES)
        self.assertIn(DOMAIN, BUILTIN_SCHEMA_PREDICATES)
        self.assertIn(RANGE, BUILTIN_SCHEMA_PREDICATES)
        self.assertIn(DISJOINT_WITH, BUILTIN_SCHEMA_PREDICATES)
        self.assertIn(ACYCLIC, BUILTIN_SCHEMA_PREDICATES)

    def test_add_and_query_assertions(self):
        model = OntologyModel(uri="urn:test:animals")
        prov = Provenance(source="unit_test", turn_id="t1")
        rel1 = Relation(subject="cat", predicate=SUBCLASS_OF, object="mammal")
        asrt1 = model.add_assertion(rel1, prov)

        rel2 = Relation(subject="felix", predicate=INSTANCE_OF, object="cat")
        asrt2 = model.add_assertion(rel2, prov)

        self.assertIn("cat", model.entities)
        self.assertIn("mammal", model.entities)
        self.assertIn("felix", model.entities)

        # Query all
        all_asrts = model.query()
        self.assertEqual(len(all_asrts), 2)

        # Query by subject
        cat_asrts = model.query(subject="cat")
        self.assertEqual(len(cat_asrts), 1)
        self.assertEqual(cat_asrts[0].relation.object, "mammal")

        # Query by predicate
        subclasses = model.query(predicate=SUBCLASS_OF)
        self.assertEqual(len(subclasses), 1)
        self.assertEqual(subclasses[0].assertion_id, asrt1.assertion_id)

    def test_retract_assertion(self):
        model = OntologyModel()
        prov = Provenance(source="test", turn_id="turn_42")
        asrt = model.add_assertion(Relation("a", "rel", "b"), prov)

        self.assertEqual(len(model.query()), 1)
        retracted = model.retract_assertion(asrt.assertion_id)
        self.assertIsNotNone(retracted)
        self.assertEqual(len(model.query()), 0)

    def test_retract_by_turn_id(self):
        model = OntologyModel()
        p1 = Provenance(source="test", turn_id="turn_1")
        p2 = Provenance(source="test", turn_id="turn_2")

        a1 = model.add_assertion(Relation("x", "r", "y"), p1)
        a2 = model.add_assertion(Relation("y", "r", "z"), p1)
        a3 = model.add_assertion(Relation("z", "r", "w"), p2)

        self.assertEqual(len(model.query()), 3)
        retracted = model.retract_by_turn_id("turn_1")
        self.assertEqual(len(retracted), 2)
        remaining = model.query()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].assertion_id, a3.assertion_id)

    def test_roundtrip_dict(self):
        model = OntologyModel(uri="urn:test:dict")
        prov = Provenance(source="test", turn_id="t1", parent_turn_ids=("t0",))
        model.add_assertion(
            Relation("doc", "mentions", "topic"),
            prov,
            attributes={"weight": 0.95},
        )

        d = model.to_dict()
        restored = OntologyModel.from_dict(d)

        self.assertEqual(restored.uri, model.uri)
        self.assertEqual(len(restored.assertions), 1)
        asrt = list(restored.assertions.values())[0]
        self.assertEqual(asrt.relation.subject, "doc")
        self.assertEqual(asrt.provenance.parent_turn_ids, ("t0",))
        self.assertEqual(asrt.attributes["weight"], 0.95)

    def test_upsert_entity_and_immutability(self):
        model = OntologyModel(uri="urn:test:upsert")
        ent = model.upsert_entity("sky_scout", name="Sky Scout v1", payload_kg=5)
        self.assertEqual(ent.name, "Sky Scout v1")
        self.assertEqual(ent.attributes["payload_kg"], 5)
        self.assertEqual(model.version, 1)

        # In-place mutation must raise TypeError
        with self.assertRaises(TypeError):
            ent.attributes["payload_kg"] = 10

        # Upsert with new attributes merges and bumps version
        ent2 = model.upsert_entity("sky_scout", range_km=25)
        self.assertEqual(ent2.name, "Sky Scout v1")
        self.assertEqual(ent2.attributes["payload_kg"], 5)
        self.assertEqual(ent2.attributes["range_km"], 25)
        self.assertEqual(model.version, 2)

        # Name override
        ent3 = model.upsert_entity("sky_scout", name="Sky Scout v2")
        self.assertEqual(ent3.name, "Sky Scout v2")
        self.assertEqual(ent3.attributes["range_km"], 25)
        self.assertEqual(model.version, 3)


if __name__ == "__main__":
    unittest.main()
