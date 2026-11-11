import json
import tempfile
import unittest
from pathlib import Path

from ontology_spider.model import OntologyModel, Provenance, Relation
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

    def test_import_cycle_detection(self):
        from ontology_spider.seam import DialogModelSource, ImportCycleError

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            file_a = tmppath / "a.dialog"
            file_b = tmppath / "b.dialog"

            file_a.write_text("dialog urn:a\nimport b.dialog\nassert a_item instance_of entity\n", encoding="utf-8")
            file_b.write_text("dialog urn:b\nimport a.dialog\nassert b_item instance_of entity\n", encoding="utf-8")

            source = DialogModelSource(file_a)
            with self.assertRaises(ImportCycleError) as ctx:
                source.load()

            self.assertIn("Cyclic import detected", str(ctx.exception))
            self.assertIn("a.dialog", str(ctx.exception))
            self.assertIn("b.dialog", str(ctx.exception))

    def test_diamond_dag_import_allowed(self):
        from ontology_spider.seam import DialogModelSource

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            base_file = tmppath / "d.dialog"
            mod_b = tmppath / "b.dialog"
            mod_c = tmppath / "c.dialog"
            top_a = tmppath / "a.dialog"

            base_file.write_text("dialog urn:d\nassert base_item instance_of entity\n", encoding="utf-8")
            mod_b.write_text("dialog urn:b\nimport d.dialog\nassert b_item instance_of entity\n", encoding="utf-8")
            mod_c.write_text("dialog urn:c\nimport d.dialog\nassert c_item instance_of entity\n", encoding="utf-8")
            top_a.write_text("dialog urn:a\nimport b.dialog\nimport c.dialog\nassert a_item instance_of entity\n", encoding="utf-8")

            source = DialogModelSource(top_a)
            model = source.load()
            self.assertIn("base_item", model.entities)
            self.assertIn("b_item", model.entities)
            self.assertIn("c_item", model.entities)
            self.assertIn("a_item", model.entities)


if __name__ == "__main__":
    unittest.main()
