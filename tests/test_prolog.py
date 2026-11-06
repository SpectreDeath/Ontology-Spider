import unittest

from ontology_spider.dialog_runner import DialogSession
from ontology_spider.model import (
    Assertion,
    Entity,
    OntologyModel,
    Provenance,
    Relation,
    INSTANCE_OF,
    SUBCLASS_OF,
)
from ontology_spider.prolog.reasoner import (
    PrologExecutionError,
    PrologReasoner,
    QueryInferenceLimitError,
    QueryTimeoutError,
    find_swipl_executable,
)
from ontology_spider.prolog.translator import (
    model_to_prolog_facts,
    prolog_facts_to_model,
)


class TestPrologReasoner(unittest.TestCase):
    def setUp(self):
        self.reasoner = PrologReasoner()
        if not self.reasoner.is_available:
            self.skipTest("swipl not available on this system")

    def test_roundtrip_translation(self):
        model = OntologyModel(uri="urn:test:roundtrip")
        model.add_entity(Entity(id="dog", attributes={"carnivore": "true", "legs": 4}))
        p = Provenance(source="test_roundtrip")
        model.add_assertion(
            Relation("dog", SUBCLASS_OF, "mammal"),
            p,
            assertion_id="a1",
            attributes={"confidence": 0.95},
        )
        model.add_assertion(Relation("mammal", SUBCLASS_OF, "animal"), p, assertion_id="a2")

        facts = model_to_prolog_facts(model)
        reconstructed = prolog_facts_to_model(facts, uri=model.uri)

        self.assertEqual(len(reconstructed.assertions), 2)
        self.assertIn("a1", reconstructed.assertions)
        self.assertIn("a2", reconstructed.assertions)
        self.assertEqual(
            reconstructed.assertions["a1"].relation.subject, "dog"
        )
        self.assertEqual(reconstructed.assertions["a1"].attributes.get("confidence"), 0.95)
        self.assertEqual(reconstructed.get_entity("dog").attributes.get("legs"), 4)

    def test_roundtrip_control_characters_and_newlines(self):
        model = OntologyModel(uri="urn:test:escaping")
        multi_line_val = "line1\nline2\r\nline3\twith tabs and 'quotes' and \\backslashes\\"
        model.upsert_entity("ent_complex", note=multi_line_val)
        p = Provenance(source="test_escaping")
        model.add_assertion(
            Relation("ent_complex", "has_data", "data_node"),
            p,
            assertion_id="asrt_esc",
            attributes={"payload": multi_line_val},
        )

        facts = model_to_prolog_facts(model)
        reconstructed = prolog_facts_to_model(facts, uri=model.uri)

        self.assertIn("ent_complex", reconstructed.entities)
        self.assertEqual(
            reconstructed.get_entity("ent_complex").attributes["note"],
            multi_line_val,
        )
        self.assertIn("asrt_esc", reconstructed.assertions)
        self.assertEqual(
            reconstructed.assertions["asrt_esc"].attributes["payload"],
            multi_line_val,
        )

        # Also test with live Prolog query
        res = self.reasoner.query(model, goal_type="pattern", subject="ent_complex")
        self.assertEqual(len(res.answers), 1)

    def test_control_character_xnn_roundtrip(self):
        from ontology_spider.prolog.translator import prolog_safe_string, unescape_prolog_atom
        test_str = "prefix_\x00_\x01_\x1f_\x7f_suffix"
        safe = prolog_safe_string(test_str)
        self.assertIn(r"\x00", safe)
        self.assertIn(r"\x01", safe)
        self.assertIn(r"\x1f", safe)
        self.assertIn(r"\x7f", safe)
        restored = unescape_prolog_atom(safe)
        self.assertEqual(restored, test_str)


    def test_ancestor_reasoning_and_provenance(self):
        model = OntologyModel(uri="urn:test:ancestry")
        p = Provenance(source="dialog_turn_1", turn_id="t1")
        asrt1 = model.add_assertion(Relation("cat", SUBCLASS_OF, "mammal"), p)
        asrt2 = model.add_assertion(Relation("mammal", SUBCLASS_OF, "animal"), p)
        asrt3 = model.add_assertion(Relation("felix", INSTANCE_OF, "cat"), p)

        res = self.reasoner.query(model, goal_type="ancestors", subject="felix")
        self.assertTrue(len(res.answers) >= 3)

        ancestor_vals = [ans.value for ans in res.answers]
        self.assertIn("cat", ancestor_vals)
        self.assertIn("mammal", ancestor_vals)
        self.assertIn("animal", ancestor_vals)

        # Check explanation trace on animal
        animal_ans = next(a for a in res.answers if a.value == "animal")
        self.assertIn("ancestor_rule", animal_ans.explanation.rules_fired)
        self.assertEqual(animal_ans.explanation.path, ["felix", "cat", "mammal", "animal"])
        self.assertEqual(len(animal_ans.explanation.provenance_assertions), 3)

    def test_cycle_guard_in_transitive(self):
        # Directed graph with cycle: a -> b -> c -> a
        model = OntologyModel(uri="urn:test:cycles")
        p = Provenance(source="cycle_test")
        model.add_assertion(Relation("a", "rel", "b"), p)
        model.add_assertion(Relation("b", "rel", "c"), p)
        model.add_assertion(Relation("c", "rel", "a"), p)

        # Transitive query from 'a' should terminate cleanly without infinite recursion
        res = self.reasoner.query(
            model,
            goal_type="transitive",
            subject="a",
            predicate="rel",
            timeout_seconds=3,
        )
        targets = [ans.value for ans in res.answers]
        self.assertIn("b", targets)
        self.assertIn("c", targets)

    def test_timeout_on_infinite_loop(self):
        model = OntologyModel(uri="urn:test:timeout")
        with self.assertRaises(QueryTimeoutError):
            self.reasoner.query(
                model,
                goal_type="infinite_loop_test",
                timeout_seconds=1,
                max_inferences=10**10,
            )

    def test_inference_limit_on_infinite_loop(self):
        model = OntologyModel(uri="urn:test:inferences")
        with self.assertRaises(QueryInferenceLimitError):
            self.reasoner.query(
                model,
                goal_type="infinite_loop_test",
                timeout_seconds=10,
                max_inferences=1000,
            )

    def test_state_isolation_between_models(self):
        m1 = OntologyModel(uri="urn:test:m1")
        m1.add_assertion(Relation("apple", "color", "red"), Provenance(source="m1"))

        m2 = OntologyModel(uri="urn:test:m2")
        m2.add_assertion(Relation("sky", "color", "blue"), Provenance(source="m2"))

        # Query pattern on m2 should not find apple
        res = self.reasoner.query(m2, goal_type="pattern", subject="apple")
        self.assertEqual(len(res.answers), 0)

        res2 = self.reasoner.query(m2, goal_type="pattern", subject="sky")
        self.assertEqual(len(res2.answers), 1)

    def test_max_results_cap(self):
        model = OntologyModel(uri="urn:test:max_results")
        p = Provenance(source="test")
        model.add_assertion(Relation("a", "subclass_of", "b"), p)
        model.add_assertion(Relation("b", "subclass_of", "c"), p)
        model.add_assertion(Relation("c", "subclass_of", "d"), p)

        # Cap results at 2 when query produces 3 answers
        limited_reasoner = PrologReasoner(max_results=2)
        with self.assertRaises(PrologExecutionError) as ctx:
            limited_reasoner.query(model, goal_type="ancestors", subject="a")
        self.assertIn("exceeds max_results cap", str(ctx.exception))

    def test_facts_translation_caching(self):
        model = OntologyModel(uri="urn:test:caching")
        p = Provenance(source="test")
        model.add_assertion(Relation("cat", "subclass_of", "mammal"), p)

        self.assertEqual(len(self.reasoner._facts_cache), 0)
        self.reasoner.query(model, goal_type="ancestors", subject="cat")

        cache_key = (model.uuid, model.version)
        self.assertIn(cache_key, self.reasoner._facts_cache)

        # Mutate model -> version changes
        old_version = model.version
        model.add_assertion(Relation("mammal", "subclass_of", "animal"), p)
        self.assertGreater(model.version, old_version)

        # Query again -> caches new version
        self.reasoner.query(model, goal_type="ancestors", subject="cat")
        new_cache_key = (model.uuid, model.version)
        self.assertIn(new_cache_key, self.reasoner._facts_cache)

    def test_facts_cache_bounded_lru(self):
        # Fill cache past capacity of 8
        models = [OntologyModel(uri=f"urn:test:lru:{i}") for i in range(12)]
        p = Provenance(source="test")
        for i, m in enumerate(models):
            m.add_assertion(Relation(f"item_{i}", "subclass_of", "root"), p)
            self.reasoner.query(m, goal_type="ancestors", subject=f"item_{i}")

        self.assertLessEqual(len(self.reasoner._facts_cache), 8)
        # Most recent model must be in cache, oldest must have been evicted
        self.assertIn((models[-1].uuid, models[-1].version), self.reasoner._facts_cache)
        self.assertNotIn((models[0].uuid, models[0].version), self.reasoner._facts_cache)

    def test_degraded_python_fallback(self):
        model = OntologyModel(uri="urn:test:degraded")
        p = Provenance(source="test")
        model.add_assertion(Relation("hummingbird", SUBCLASS_OF, "bird"), p)
        model.add_assertion(Relation("bird", SUBCLASS_OF, "animal"), p)
        model.add_assertion(Relation("fluffy", INSTANCE_OF, "hummingbird"), p)

        dummy_reasoner = PrologReasoner(swipl_path="C:\\nonexistent\\swipl.exe")
        session = DialogSession(model=model, reasoner=dummy_reasoner, allow_degraded_fallback=True)

        # Ancestors query in degraded mode
        turn_res = session.run_text("query ancestors of fluffy")[0]
        self.assertIn("[Degraded Mode: swipl unavailable]", turn_res.summary_text)
        self.assertEqual(len(turn_res.answers), 3)
        self.assertIn("degraded_python_fallback", turn_res.answers[0].explanation.rules_fired)


if __name__ == "__main__":
    unittest.main()
