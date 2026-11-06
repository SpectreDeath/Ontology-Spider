import re
import unittest
from pathlib import Path

from ontology_spider.api import export_model, load_model, run_query, validate_model
from ontology_spider.cli import run_batch
from ontology_spider.dialog import parse_dialog


class TestDocsVerbatim(unittest.TestCase):
    """Verifies that code examples in documentation execute verbatim without error."""

    def setUp(self):
        self.root = Path(__file__).resolve().parent.parent
        self.tutorial_dialog = self.root / "examples" / "tutorial.dialog"
        self.assertTrue(self.tutorial_dialog.exists())

    def test_tutorial_cli_run_verbatim(self):
        exit_code = run_batch(str(self.tutorial_dialog))
        self.assertEqual(exit_code, 0)

    def test_tutorial_python_api_verbatim(self):
        # Snippet from docs/tutorial.md Section 2:
        model = load_model(str(self.tutorial_dialog))
        self.assertIsNotNone(model)

        result = run_query(model, "query ancestors of delivery_drone")
        self.assertEqual(result["statement_type"], "query")
        self.assertTrue(len(result["answers"]) >= 3)

        violations = validate_model(model)
        self.assertIsInstance(violations, list)

        html_view = export_model(model, "html")
        self.assertIn("<!DOCTYPE html>", html_view)

    def test_readme_python_snippet_verbatim(self):
        # Snippet from README.md Section "Python API"
        model = load_model(self.root / "examples" / "drones.dialog")
        violations = validate_model(model)
        self.assertIsInstance(violations, list)

        result = run_query(model, "query recommend delivery_drone [payload_kg=5]")
        answers = [a["value"] for a in result["answers"]]
        self.assertIn("sky_scout", answers)
        self.assertTrue(len(result["answers"]) > 0)
        first_trace = result["answers"][0]
        self.assertIn("rules_fired", first_trace)
        self.assertIn("path", first_trace)

        json_str = export_model(model, "json")
        self.assertTrue(json_str.startswith("{"))
        html_str = export_model(model, "html")
        self.assertIn("<!DOCTYPE html>", html_str)

    def test_all_fenced_dialog_blocks_parse(self):
        doc_files = [
            self.root / "README.md",
            self.root / "docs" / "language_reference.md",
        ]
        dialog_block_re = re.compile(r"```dialog\s*\n(.*?)\n\s*```", re.DOTALL)

        for doc_path in doc_files:
            text = doc_path.read_text(encoding="utf-8")
            blocks = dialog_block_re.findall(text)
            for idx, block in enumerate(blocks, start=1):
                clean_block = block.strip()
                if not clean_block:
                    continue
                # If block has no header, prepend dummy header
                if not (clean_block.startswith("dialog ") or clean_block.startswith("ontology ")):
                    clean_block = f"dialog urn:test:snippet\n{clean_block}"
                try:
                    parsed = parse_dialog(clean_block)
                    self.assertIsNotNone(parsed)
                except Exception as err:
                    self.fail(f"Failed parsing dialog block #{idx} in {doc_path.name}:\n{block}\nError: {err}")


if __name__ == "__main__":
    unittest.main()
