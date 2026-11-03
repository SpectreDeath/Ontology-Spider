import json
import unittest
from pathlib import Path

from ontology_spider.dialog_runner import DialogSession


class TestCorpusTutorial(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent.parent
        self.dialog_path = root / "examples" / "tutorial.dialog"
        self.expected_path = root / "examples" / "expected_tutorial_answers.json"
        self.assertTrue(self.dialog_path.exists())
        self.assertTrue(self.expected_path.exists())

    def test_tutorial_corpus_answers_match_expected(self):
        session = DialogSession()
        results = session.run_file(self.dialog_path)

        query_results = [r for r in results if r.statement_type == "query"]
        with open(self.expected_path, "r", encoding="utf-8") as f:
            expected_data = json.load(f)["answers"]

        self.assertEqual(len(query_results), len(expected_data))

        for q_res, exp in zip(query_results, expected_data):
            actual_vals = [str(a.value) for a in q_res.answers]
            for ev in exp["expected_values"]:
                self.assertIn(
                    ev,
                    actual_vals,
                    f"Expected value '{ev}' not found in query results: {actual_vals}",
                )

        # Ensure the final explain statement produced explanations
        explain_res = results[-1]
        self.assertEqual(explain_res.statement_type, "explain")
        self.assertIn("Explanation", explain_res.summary_text)


if __name__ == "__main__":
    unittest.main()
