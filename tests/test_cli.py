import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ontology_spider.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmppath = Path(self.tmpdir.name)
        self.valid_dialog = self.tmppath / "test.dialog"
        self.valid_dialog.write_text(
            """dialog urn:test:cli
entity quad_1 [speed=50]
assert quad_1 instance_of drone
query what is quad_1?
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_cli_run_batch(self):
        exit_code = main(["run", str(self.valid_dialog)])
        self.assertEqual(exit_code, 0)

        # File not found
        exit_code_missing = main(["run", str(self.tmppath / "missing.dialog")])
        self.assertEqual(exit_code_missing, 1)

    def test_cli_validate(self):
        exit_code = main(["validate", str(self.valid_dialog)])
        # Valid file
        self.assertEqual(exit_code, 0)

        # File with cycle violation
        invalid_dialog = self.tmppath / "invalid.dialog"
        invalid_dialog.write_text(
            """dialog urn:test:inv
assert a subclass_of b
assert b subclass_of a
""",
            encoding="utf-8",
        )
        exit_code_inv = main(["validate", str(invalid_dialog)])
        self.assertEqual(exit_code_inv, 1)

        exit_code_missing = main(["validate", str(self.tmppath / "missing.dialog")])
        self.assertEqual(exit_code_missing, 1)

    def test_cli_export(self):
        # Print to stdout
        exit_code_stdout = main(["export", str(self.valid_dialog), "--format", "json"])
        self.assertEqual(exit_code_stdout, 0)

        out_json = self.tmppath / "out.json"
        exit_code = main(["export", str(self.valid_dialog), "--format", "json", "-o", str(out_json)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(out_json.is_file())
        self.assertIn("quad_1", out_json.read_text(encoding="utf-8"))

        out_html = self.tmppath / "out.html"
        exit_code_html = main(["export", str(self.valid_dialog), "--format", "html", "-o", str(out_html)])
        self.assertEqual(exit_code_html, 0)
        self.assertTrue(out_html.is_file())
        self.assertIn("<!DOCTYPE html>", out_html.read_text(encoding="utf-8"))

        # Missing file
        exit_code_missing = main(["export", str(self.tmppath / "missing.dialog")])
        self.assertEqual(exit_code_missing, 1)

    def test_cli_elicit(self):
        inputs = [
            "",            # Empty line
            "Test Topic",  # Decision Question
            "done",        # Competency Question
            "plane subclass_of vehicle", # Class
            "y",           # Confirm
            "done",        # Done classes
            "done",        # Done relations
            "cessna instance_of plane [speed=200]", # Instance
            "y",           # Confirm
            "done",        # Done instances -> Complete
        ]
        out_dialog = self.tmppath / "elicited.dialog"
        with patch("builtins.input", side_effect=inputs):
            exit_code = main(["elicit", "-o", str(out_dialog)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(out_dialog.is_file())
        content = out_dialog.read_text(encoding="utf-8")
        self.assertIn("plane", content)
        self.assertIn("cessna", content)

        # Early exit
        with patch("builtins.input", side_effect=["exit"]):
            exit_code_exit = main(["elicit"])
        self.assertEqual(exit_code_exit, 0)

    def test_cli_repl_interactions(self):
        inputs = [
            "",
            "where am i",
            "assert car subclass_of vehicle",
            "focus car",
            "constrain wheels=4",
            "constrain invalid_no_equals",
            "validate",
            "export dialog",
            "export invalid_format_xyz",
            "query what is car?",
            "explain",
            "assert sedan instance_of car [wheels=4]",
            "query recommend car",
            "explain",
            "malformed syntax %%%",
            "quit",
        ]
        buf = io.StringIO()
        with patch("builtins.input", side_effect=inputs), contextlib.redirect_stdout(buf):
            exit_code = main(["repl", "--file", str(self.valid_dialog)])
        out = buf.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("[frame-filtered: 0 remaining]", out)
        self.assertIn("No preceding query answer to explain.", out)
        self.assertIn("sedan", out)
        self.assertIn("Explanation for previous answers:", out)
        self.assertIn("sedan instance_of car", out)

    def test_module_main(self):
        import runpy
        buf = io.StringIO()
        with patch("sys.argv", ["ontology_spider", "--help"]), patch("sys.exit") as mock_exit, contextlib.redirect_stdout(buf):
            runpy.run_module("ontology_spider", run_name="__main__")
            mock_exit.assert_called_with(0)


if __name__ == "__main__":
    unittest.main()
