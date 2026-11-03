import ast
import unittest
from pathlib import Path


class TestSeamIsolation(unittest.TestCase):
    """Automated AST/import inspection test ensuring seam carries zero brain-harness code."""

    def test_seam_imports_and_tokens_clean(self):
        root = Path(__file__).resolve().parent.parent / "src" / "ontology_spider"
        target_files = [root / "seam.py", root / "model.py"]

        for file_path in target_files:
            self.assertTrue(file_path.exists(), f"Target file does not exist: {file_path}")
            source_text = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source_text, filename=str(file_path))

            # Check all imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(
                            "brain_harness",
                            alias.name.lower(),
                            f"Illegal import in {file_path.name}: {alias.name}",
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        self.assertNotIn(
                            "brain_harness",
                            node.module.lower(),
                            f"Illegal from-import in {file_path.name}: {node.module}",
                        )

            # Check that prohibited domain terms are not in identifiers or fields
            prohibited_terms = {"brain_harness", "brainharness", "vault_export"}
            lower_source = source_text.lower()
            for term in prohibited_terms:
                self.assertNotIn(
                    term,
                    lower_source,
                    f"Found prohibited brain-harness specific token '{term}' in {file_path.name}",
                )


if __name__ == "__main__":
    unittest.main()
