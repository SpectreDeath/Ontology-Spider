import tempfile
import unittest
from pathlib import Path

from ontology_spider.cli import run_batch
from ontology_spider.dialog_runner import DialogSession


class TestCliAndRunner(unittest.TestCase):
    def setUp(self):
        self.sample_dialog = """dialog urn:test:animals
assert cat subclass_of mammal
assert mammal subclass_of animal
assert felix instance_of cat

query what is felix?
query ancestors of cat
query transitive subclass_of from cat
explain
"""

    def test_runner_batch_execution(self):
        session = DialogSession()
        results = session.run_text(self.sample_dialog)

        self.assertEqual(len(results), 7)
        # 3 assertions
        self.assertEqual(results[0].statement_type, "assertion")
        self.assertEqual(results[1].statement_type, "assertion")
        self.assertEqual(results[2].statement_type, "assertion")

        # 3 queries
        self.assertEqual(results[3].statement_type, "query")
        self.assertTrue(len(results[3].answers) >= 1)

        # ancestors of cat
        self.assertEqual(results[4].statement_type, "query")
        anc_vals = [str(a.value) for a in results[4].answers]
        self.assertIn("mammal", anc_vals)
        self.assertIn("animal", anc_vals)

        # explain
        self.assertEqual(results[6].statement_type, "explain")
        self.assertIn("Explanation", results[6].summary_text)

    def test_batch_and_interactive_parity(self):
        # Run in batch
        batch_session = DialogSession()
        batch_results = batch_session.run_text(self.sample_dialog)

        # Run turn-by-turn interactive style
        interactive_session = DialogSession()
        interactive_results = []
        for line in self.sample_dialog.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("dialog"):
                continue
            res = interactive_session.run_text(f"dialog urn:test\n{line}")
            interactive_results.extend(res)

        self.assertEqual(len(batch_results), len(interactive_results))
        for b_res, i_res in zip(batch_results, interactive_results):
            self.assertEqual(b_res.statement_type, i_res.statement_type)
            self.assertEqual(len(b_res.answers), len(i_res.answers))

    def test_cli_run_batch_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".dialog", delete=False) as f:
            f.write(self.sample_dialog)
            path = Path(f.name)

        try:
            exit_code = run_batch(str(path))
            self.assertEqual(exit_code, 0)
        finally:
            if path.is_file():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
