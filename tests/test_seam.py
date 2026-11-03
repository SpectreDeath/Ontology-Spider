import json
import tempfile
import unittest
from pathlib import Path

from ontology_spider.model import OntologyModel, Relation, Provenance
from ontology_spider.seam import JsonModelSource, ModelSource


class TestSeam(unittest.TestCase):
    def test_json_model_source_string(self):
        payload = json.dumps({
            "uri": "urn:ontology:test",
            "entities": [{"id": "itemA", "name": "Item A"}],
            "assertions": [
                {
                    "assertion_id": "asrt_100",
                    "relation": {
                        "subject": "itemA",
                        "predicate": "depends_on",
                        "object": "itemB",
                    },
                    "provenance": {
                        "source": "memory",
                        "timestamp": "2026-11-03T12:00:00Z",
                    },
                    "attributes": {},
                }
            ],
        })

        source: ModelSource = JsonModelSource(payload)
        model = source.load()
        self.assertEqual(model.uri, "urn:ontology:test")
        self.assertIn("itemA", model.entities)
        self.assertIn("itemB", model.entities)
        self.assertEqual(len(model.query()), 1)

    def test_json_model_source_file(self):
        model = OntologyModel(uri="urn:ontology:file_test")
        model.add_assertion(
            Relation("x", "connected_to", "y"),
            Provenance(source="seed_file"),
            assertion_id="seed_1",
        )

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(model.to_dict(), f)
            temp_path = Path(f.name)

        try:
            source = JsonModelSource(temp_path)
            loaded_model = source.load()
            self.assertEqual(loaded_model.uri, "urn:ontology:file_test")
            self.assertEqual(len(loaded_model.query()), 1)
            self.assertEqual(loaded_model.query()[0].assertion_id, "seed_1")
        finally:
            if temp_path.is_file():
                temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
