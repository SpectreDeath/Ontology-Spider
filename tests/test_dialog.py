import tempfile
import unittest
from pathlib import Path

from ontology_spider.dialog import (
    DialogAssertion,
    DialogDoc,
    DialogImport,
    DialogQuery,
    ParseError,
    parse_dialog,
)
from ontology_spider.seam import DialogModelSource


class TestDialog(unittest.TestCase):
    def test_parse_valid_dialog(self):
        sample = """
        # Comments are ignored
        dialog urn:ontology:vehicles

        import "common.json"

        assert car subclass_of vehicle [wheels=4, motorized=true]
        assert bicycle subclass_of vehicle [wheels=2, motorized=false]
        assert my_prius instance_of car

        query what is my_prius?
        query ancestors of car
        query transitive subclass_of from car
        query filter subclass_of where wheels=4
        query ? subclass_of vehicle?
        explain
        """
        doc = parse_dialog(sample)
        self.assertEqual(doc.uri, "urn:ontology:vehicles")
        self.assertEqual(len(doc.imports), 1)
        self.assertEqual(doc.imports[0].path, "common.json")

        assertions = [s for s in doc.statements if isinstance(s, DialogAssertion)]
        self.assertEqual(len(assertions), 3)
        self.assertEqual(assertions[0].subject, "car")
        self.assertEqual(assertions[0].attributes["wheels"], 4)

        queries = [s for s in doc.statements if isinstance(s, DialogQuery)]
        self.assertEqual(len(queries), 6)
        self.assertEqual(queries[0].kind, "lookup")
        self.assertEqual(queries[0].subject, "my_prius")
        self.assertEqual(queries[1].kind, "ancestors")
        self.assertEqual(queries[2].kind, "transitive")
        self.assertEqual(queries[3].kind, "filter")
        self.assertEqual(queries[4].kind, "pattern")
        self.assertEqual(queries[5].kind, "explain")

    def test_parse_error_reporting(self):
        malformed = """dialog urn:test
assert only_two_tokens
"""
        with self.assertRaises(ParseError) as ctx:
            parse_dialog(malformed)

        err_msg = str(ctx.exception)
        self.assertIn("Line 2", err_msg)
        self.assertIn("expected", err_msg.lower())

    def test_dialog_model_source_loading(self):
        dialog_content = """dialog urn:test:animals
assert lion subclass_of feline
assert feline subclass_of mammal
"""
        source = DialogModelSource(dialog_content)
        model = source.load()

        self.assertEqual(model.uri, "urn:test:animals")
        self.assertEqual(len(model.assertions), 2)
        asrts = model.query(predicate="subclass_of")
        self.assertEqual(len(asrts), 2)
        # Verify provenance was attached
        self.assertTrue(all(a.provenance.source == "inline.dialog" for a in asrts))


if __name__ == "__main__":
    unittest.main()
