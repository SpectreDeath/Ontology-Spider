import unittest

from ontology_spider.api import export_model, load_model, run_query, validate_model
from ontology_spider.model import Entity, OntologyModel, Provenance, Relation, SUBCLASS_OF, INSTANCE_OF


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


if __name__ == "__main__":
    unittest.main()
