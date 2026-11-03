import ast
import unittest
from pathlib import Path

from examples.vault_adapter import VaultModelSource
from ontology_spider.api import run_query


class TestTrack9SeamProof(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent.parent
        self.sample_json = root / "examples" / "vault_sample.json"
        self.adapter_file = root / "examples" / "vault_adapter.py"
        self.assertTrue(self.sample_json.exists())
        self.assertTrue(self.adapter_file.exists())

    def test_vault_sample_loads_and_answers_traversal_queries(self):
        source = VaultModelSource(self.sample_json)
        model = source.load()

        self.assertEqual(model.uri, "urn:vault:demo_vault")
        self.assertIn("spec_core", model.entities)
        self.assertIn("spec_seam", model.entities)
        self.assertIn("impl_plugin", model.entities)

        # Transitive dependency query: impl_plugin -> spec_seam -> spec_core
        res = run_query(model, "query transitive depends_on from impl_plugin")
        self.assertEqual(res["statement_type"], "query")
        dep_vals = [a["value"] for a in res["answers"]]
        self.assertIn("spec_seam", dep_vals)
        self.assertIn("spec_core", dep_vals)

        # Verify explanation on spec_core
        core_ans = next(a for a in res["answers"] if a["value"] == "spec_core")
        self.assertEqual(
            core_ans["path"],
            ["impl_plugin", "spec_seam", "spec_core"],
        )
        self.assertIn("transitive_closure", core_ans["rules_fired"])

    def test_adapter_zero_brain_harness_imports(self):
        source_text = self.adapter_file.read_text(encoding="utf-8")
        tree = ast.parse(source_text, filename=str(self.adapter_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn("brain_harness", alias.name.lower())
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.assertNotIn("brain_harness", node.module.lower())


if __name__ == "__main__":
    unittest.main()
