import unittest

from ontology_spider.api import (
    evaluate_competency_questions,
    export_model,
    load_model,
    rank_discriminating_attributes,
    run_query,
    validate_model,
)
from ontology_spider.elicitation import ElicitationManager
from ontology_spider.model import (
    INSTANCE_OF,
    SUBCLASS_OF,
    Entity,
    OntologyModel,
    Provenance,
    Relation,
)


class TestApiAndExport(unittest.TestCase):
    def setUp(self):
        self.model = OntologyModel(uri="urn:test:export")
        p = Provenance(source="test_api", turn_id="turn_api_1")
        self.model.add_assertion(Relation("sparrow", SUBCLASS_OF, "bird"), p, assertion_id="a_sparrow")
        self.model.add_assertion(Relation("bird", SUBCLASS_OF, "vertebrate"), p, assertion_id="a_bird")
        self.model.add_assertion(Relation("jack", INSTANCE_OF, "sparrow"), p, assertion_id="a_jack")

    def test_run_query_api(self):
        res = run_query(self.model, "query ancestors of jack")
        self.assertEqual(res["statement_type"], "query")
        self.assertTrue(len(res["answers"]) >= 3)
        ans_values = [a["value"] for a in res["answers"]]
        self.assertIn("sparrow", ans_values)
        self.assertIn("bird", ans_values)
        self.assertIn("vertebrate", ans_values)

        # Verify provenance was returned in machine API
        first_ans = res["answers"][0]
        self.assertTrue(len(first_ans["provenance"]) >= 1)

    def test_validate_model_api(self):
        violations = validate_model(self.model)
        # Should return a list of dicts
        self.assertIsInstance(violations, list)

    def test_roundtrip_json_export_and_import(self):
        json_str = export_model(self.model, "json")
        reimported = load_model(json_str)

        self.assertEqual(reimported.uri, self.model.uri)
        self.assertEqual(len(reimported.assertions), len(self.model.assertions))

        orig_query = run_query(self.model, "query ancestors of jack")
        reimport_query = run_query(reimported, "query ancestors of jack")
        self.assertEqual(
            [a["value"] for a in orig_query["answers"]],
            [a["value"] for a in reimport_query["answers"]],
        )

    def test_roundtrip_dialog_export_and_import(self):
        # Add entity with attributes and assertion with custom attributes
        self.model.add_entity(Entity(id="jack", name="Jack Sparrow", attributes={"wingspan_cm": 25}))
        p = Provenance(source="custom_turn_source", turn_id="t99")
        self.model.add_assertion(
            Relation("jack", "flies_speed", "fast"),
            p,
            assertion_id="asrt_speed_jack",
            attributes={"metric": "high"},
        )

        dialog_str = export_model(self.model, "dialog")
        reimported = load_model(dialog_str)

        self.assertEqual(reimported.uri, self.model.uri)
        self.assertEqual(len(reimported.assertions), len(self.model.assertions))

        # Check entity attributes preserved
        jack_ent = reimported.get_entity("jack")
        self.assertIsNotNone(jack_ent)
        self.assertEqual(jack_ent.attributes.get("wingspan_cm"), 25)

        # Check assertion ID, attributes, and provenance preserved
        asrt_speed = reimported.assertions.get("asrt_speed_jack")
        self.assertIsNotNone(asrt_speed)
        self.assertEqual(asrt_speed.attributes.get("metric"), "high")
        self.assertEqual(asrt_speed.provenance.source, "custom_turn_source")
        self.assertEqual(asrt_speed.provenance.turn_id, "t99")

        orig_query = run_query(self.model, "query ancestors of jack")
        reimport_query = run_query(reimported, "query ancestors of jack")
        self.assertEqual(
            [a["value"] for a in orig_query["answers"]],
            [a["value"] for a in reimport_query["answers"]],
        )

    def test_dot_and_html_export(self):
        dot_str = export_model(self.model, "dot")
        self.assertIn("digraph", dot_str)
        self.assertIn("sparrow", dot_str)
        self.assertIn("bird", dot_str)

        html_str = export_model(self.model, "html")
        self.assertIn("<!DOCTYPE html>", html_str)
        self.assertIn("urn:test:export", html_str)
        self.assertIn("a_sparrow", html_str)



    def test_rank_discriminating_attributes_and_competency_evaluation(self):
        p = Provenance(source="test_api", turn_id="turn_attr")
        self.model.add_assertion(Relation("e1", INSTANCE_OF, "bird"), p)
        self.model.add_assertion(Relation("e2", INSTANCE_OF, "bird"), p)
        self.model.add_assertion(Relation("e3", INSTANCE_OF, "bird"), p)
        self.model.upsert_entity("e1", attributes={"color": "red", "tier": "a"})
        self.model.upsert_entity("e2", attributes={"color": "blue", "tier": "a"})
        self.model.upsert_entity("e3", attributes={"color": "green", "tier": "a"})

        ranked = rank_discriminating_attributes(self.model, ["e1", "e2", "e3"])
        self.assertEqual(ranked[0]["attribute"], "color")
        self.assertGreater(ranked[0]["laya_score"], ranked[1]["laya_score"])
        self.assertEqual(rank_discriminating_attributes(self.model, []), [])

        mgr = ElicitationManager(model=self.model)
        self.assertEqual(mgr.suggest_discriminating_attributes(["e1", "e2"])[0]["attribute"], "color")

        self.model.upsert_entity("e1", attributes={"tags": ["alpha"], "_internal": "skip"})
        all_ranked = rank_discriminating_attributes(self.model)
        self.assertTrue(all(item["attribute"] != "_internal" for item in all_ranked))
        empty_eval = evaluate_competency_questions(OntologyModel(uri="urn:empty"), ["  "])
        self.assertEqual(empty_eval["total_questions"], 0)

        report = evaluate_competency_questions(
            self.model,
            ["ancestors of jack", "query not jack instance_of fish"],
        )
        self.assertEqual(report["total_questions"], 2)
        self.assertEqual(report["answered_questions"], 2)
        self.assertEqual(report["violation_count"], 0)
        self.assertEqual(report["coherence"], 1.0)
        self.assertGreater(report["overall_score"], 0.5)

        cyc_model = OntologyModel(uri="urn:test:cyc")
        cyc_model.add_assertion(Relation("x", SUBCLASS_OF, "y"), p)
        cyc_model.add_assertion(Relation("y", SUBCLASS_OF, "x"), p)
        cyc_report = evaluate_competency_questions(cyc_model, ["query ancestors of x"])
        self.assertGreaterEqual(cyc_report["violation_count"], 1)
        self.assertLess(cyc_report["coherence"], 1.0)


if __name__ == "__main__":
    unittest.main()
