import unittest
from pathlib import Path

from ontology_spider.api import export_model, load_model, run_query, validate_model
from ontology_spider.cli import run_batch


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


if __name__ == "__main__":
    unittest.main()
