"""Failing-first contract tests for Ontology-Spider repo-learning & round-trip fixes."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ontology_spider.api import (
    evaluate_competency_questions,
    export_model,
    load_model,
    rank_discriminating_attributes,
    validate_model,
)
from ontology_spider.engine import Session
from ontology_spider.mcp.server import MCPServer
from ontology_spider.model import (
    ACYCLIC,
    DOMAIN,
    INSTANCE_OF,
    RANGE,
    SUBCLASS_OF,
    OntologyModel,
    Provenance,
    Relation,
)
from ontology_spider.prolog.reasoner import PrologReasoner
from ontology_spider.reasoning.python_backend import PythonReasoner
from ontology_spider.traversal import TraversalDialogueManager


class TestOntologySpiderRepoLearningFixes(unittest.TestCase):
    def test_boolean_attribute_parity_across_backends_and_dialog_roundtrip(self) -> None:
        model = OntologyModel(uri="urn:test:bool_parity")
        p = Provenance(source="test")
        model.add_assertion(Relation("sub_proj", SUBCLASS_OF, "project"), p)
        model.add_assertion(Relation("proj_a", INSTANCE_OF, "sub_proj"), p)
        model.add_assertion(Relation("proj_b", INSTANCE_OF, "sub_proj"), p)
        model.upsert_entity("proj_a", framework="jax", has_tests=True, archived=False)
        model.upsert_entity("proj_b", framework="jax", has_tests=False, archived=True)

        backends: list[tuple[str, object]] = [("python", PythonReasoner())]
        prolog = PrologReasoner()
        if prolog.is_available:
            backends.append(("prolog", prolog))

        for name, reasoner in backends:
            for query_str in (
                "query recommend project [framework=jax, has_tests=true]",
                "query recommend project [framework=jax, has_tests=True]",
                "query recommend sub_proj where has_tests=true",
                "query filter instance_of where has_tests=true",
            ):
                res = Session(model=model, reasoner=reasoner).execute(query_str)[-1]  # type: ignore[arg-type]
                vals = [a["value"] for a in res.answers]
                self.assertTrue(
                    any("proj_a" in str(v) for v in vals),
                    f"{name} failed on {query_str}: {vals}",
                )

            # TraversalDialogueManager active constraint must also handle bool/str casing
            mgr = TraversalDialogueManager(model=model, reasoner=reasoner)
            mgr.change_constraint("has_tests", "true")
            trav_res = mgr.query("query recommend project")
            self.assertEqual([a.value for a in trav_res.answers], ["proj_a"], f"{name} traversal mismatch")

        # After lossless .dialog roundtrip, both lower and upper bool queries must still match
        reloaded = load_model(export_model(model, format="dialog"))
        for name, reasoner in backends:
            for q in (
                "query recommend project [framework=jax, has_tests=true]",
                "query recommend project [framework=jax, has_tests=True]",
            ):
                res = Session(model=reloaded, reasoner=reasoner).execute(q)[-1]  # type: ignore[arg-type]
                self.assertEqual([a["value"] for a in res.answers], ["proj_a"], f"{name} roundtrip failed on {q}")

    def test_validation_cycle_includes_resolved_witness_details(self) -> None:
        model = OntologyModel(uri="urn:test:cycle_details")
        p = Provenance(source="test")
        model.add_assertion(Relation("depends_on", ACYCLIC, "true"), p)
        model.add_assertion(Relation("pkg_a", "depends_on", "pkg_b"), p)
        model.add_assertion(Relation("pkg_b", "depends_on", "pkg_a"), p)

        violations = validate_model(model)
        cyc = [v for v in violations if v["check_type"] == "cycle_violation"]
        self.assertEqual(len(cyc), 1)
        details = cyc[0]["details"]
        self.assertEqual(details.get("predicate"), "depends_on")
        self.assertIn("pkg_a", details.get("cycle_nodes", []))
        self.assertIn("pkg_b", details.get("cycle_nodes", []))
        self.assertTrue(len(details.get("cycle_edges", [])) >= 2)
        self.assertIn("->", details.get("cycle_path", ""))

    def test_entropy_ranking_demotes_unique_identifiers_on_large_populations(self) -> None:
        model = OntologyModel(uri="urn:test:entropy_cardinality")
        p = Provenance(source="test")
        for idx in range(20):
            eid = f"proj_{idx:02d}"
            model.add_assertion(Relation(eid, INSTANCE_OF, "project"), p)
            model.upsert_entity(
                eid,
                raw_name=f"unique_project_name_{idx}",
                framework="jax" if idx % 2 == 0 else "tensorflow",
                domain="nlp" if idx < 7 else ("vision" if idx < 14 else "rl"),
            )

        ranked = rank_discriminating_attributes(model, [f"proj_{i:02d}" for i in range(20)])
        self.assertTrue(len(ranked) >= 3)
        self.assertIn(ranked[0]["attribute"], ("domain", "framework"))
        raw_entry = next(r for r in ranked if r["attribute"] == "raw_name")
        self.assertTrue(raw_entry["is_identifier_like"])

    def test_competency_extendibility_not_diluted_by_instance_count(self) -> None:
        model = OntologyModel(uri="urn:test:gruber_scale")
        p = Provenance(source="test")
        model.add_assertion(Relation("sub_a", SUBCLASS_OF, "project"), p)
        model.add_assertion(Relation("sub_b", SUBCLASS_OF, "project"), p)
        model.add_assertion(Relation("uses_fw", DOMAIN, "project"), p)
        model.add_assertion(Relation("uses_fw", RANGE, "framework"), p)
        for i in range(200):
            pid = f"p_{i}"
            model.add_assertion(Relation(pid, INSTANCE_OF, "sub_a" if i % 2 == 0 else "sub_b"), p)
            model.add_assertion(Relation(pid, "uses_fw", "jax"), p)

        report = evaluate_competency_questions(model, ["query recommend project"])
        self.assertGreater(report["extendibility"], 0.3)
        self.assertGreater(report["minimal_encoding_bias"], 0.9)

    def test_mcp_server_loads_json_and_dialog_models(self) -> None:
        model = OntologyModel(uri="urn:test:mcp_json")
        p = Provenance(source="test")
        model.add_assertion(Relation("alpha", INSTANCE_OF, "project"), p)

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            json_path = root / "sample.json"
            json_path.write_text(json.dumps(model.to_dict()), encoding="utf-8")

            server = MCPServer(root_dir=root)
            res = server._handle_tools_call(
                {
                    "name": "session_open",
                    "arguments": {"session_id": "s_json", "model_path": "sample.json"},
                }
            )
            self.assertEqual(res["sessionId"], "s_json")

            q_res = server._handle_tools_call(
                {
                    "name": "query",
                    "arguments": {"session_id": "s_json", "query": "query count recommend project"},
                }
            )
            self.assertEqual(q_res["answers"][0]["value"], 1)

            # Also verify model_load with .json on an existing session
            server._handle_tools_call({"name": "session_open", "arguments": {"session_id": "s_load"}})
            load_res = server._handle_tools_call(
                {"name": "model_load", "arguments": {"session_id": "s_load", "path": "sample.json"}}
            )
            self.assertIn("Loaded model", load_res["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
