import unittest
from ontology_spider.harness.generators import (
    generate_chain,
    generate_tree,
    generate_random_dag,
    generate_lattice,
    generate_cyclic,
)
from ontology_spider.harness.properties import (
    verify_transitivity_monotonicity,
    verify_roundtrip_dialog,
    verify_roundtrip_json,
    verify_validation_cycle_detection,
    verify_frame_scoping_invariant,
)


class TestHarnessProperties(unittest.TestCase):
    def test_transitivity_monotonicity(self):
        m_chain = generate_chain(20)
        self.assertTrue(verify_transitivity_monotonicity(m_chain, "subclass_of"))

        m_tree = generate_tree(3, 3)
        self.assertTrue(verify_transitivity_monotonicity(m_tree, "subclass_of"))

    def test_roundtrip_dialog(self):
        for model in [generate_chain(10), generate_tree(10, 2), generate_random_dag(15)]:
            self.assertTrue(verify_roundtrip_dialog(model))

    def test_roundtrip_json(self):
        for model in [generate_chain(10), generate_tree(10, 2), generate_random_dag(15)]:
            self.assertTrue(verify_roundtrip_json(model))

    def test_validation_cycle_detection(self):
        clean_model = generate_random_dag(15)
        self.assertTrue(verify_validation_cycle_detection(clean_model, expect_cycle=False))

        cyclic_model = generate_cyclic(10)
        self.assertTrue(verify_validation_cycle_detection(cyclic_model, expect_cycle=True))

    def test_frame_scoping_invariant(self):
        model = generate_tree(10, 2)
        self.assertTrue(verify_frame_scoping_invariant(model))

    def test_python_reasoner_all_query_kinds(self):
        from ontology_spider.api import load_model
        from ontology_spider.reasoning.base import QuerySpec
        from ontology_spider.reasoning.python_backend import PythonReasoner

        r = PythonReasoner()
        self.assertTrue(r.is_available)
        self.assertEqual(r.name, "python")

        model = load_model("examples/drones.dialog")
        # lookup
        res_lookup = r.query(model, QuerySpec(kind="lookup", subject="sky_scout"))
        self.assertTrue(len(res_lookup.answers) >= 1)
        self.assertIn("Rules:", res_lookup.answers[0].explanation.summary())
        self.assertIsInstance(res_lookup.to_dict(), dict)

        # ancestors
        res_anc = r.query(model, QuerySpec(kind="ancestors", subject="delivery_drone"))
        self.assertIn("aerial_vehicle", [a.value for a in res_anc.answers])

        # transitive
        res_trans = r.query(model, QuerySpec(kind="transitive", subject="sky_scout", predicate="depends_on"))
        self.assertIn("gps_mod", [a.value for a in res_trans.answers])

        # pattern
        res_pat = r.query(model, QuerySpec(kind="pattern", subject="sky_scout", predicate="instance_of", object=None))
        self.assertEqual(len(res_pat.answers), 1)

        # filter
        res_flt = r.query(model, QuerySpec(kind="filter", predicate="instance_of", filter_key="payload_kg", filter_val="5"))
        self.assertTrue(len(res_flt.answers) >= 1)

        # recommend with filter and without filter
        res_rec1 = r.query(model, QuerySpec(kind="recommend", subject="aerial_vehicle", filter_key="payload_kg", filter_val="5"))
        self.assertIn("sky_scout", [a.value for a in res_rec1.answers])

        res_rec2 = r.query(model, QuerySpec(kind="recommend", subject="aerial_vehicle", filter_attributes={"payload_kg": "5"}))
        self.assertIn("sky_scout", [a.value for a in res_rec2.answers])

        res_rec3 = r.query(model, QuerySpec(kind="recommend", subject="aerial_vehicle"))
        self.assertIn("sky_scout", [a.value for a in res_rec3.answers])

        # unknown kind
        res_unk = r.query(model, QuerySpec(kind="unknown_xyz"))
        self.assertEqual(res_unk.answers, [])

    def test_engine_and_session_full(self):
        from ontology_spider.engine import Engine, Session
        from ontology_spider.reasoning.python_backend import PythonReasoner

        eng = Engine()
        self.assertIn("python", eng.available_backends)
        self.assertIn(eng.active_backend_name, ("prolog", "python"))

        s = Session(reasoner=PythonReasoner())
        self.assertEqual(s.execute(""), [])
        res_list = s.execute(
            "entity drone_x [payload_kg=10]\n"
            "assert drone_x instance_of aerial_vehicle [payload_kg=10]\n"
            "query what is drone_x?\n"
            "explain\n"
            "query recommend aerial_vehicle [payload_kg=10] explain\n"
            "query ? instance_of aerial_vehicle?\n"
            "query instance_of aerial_vehicle [payload_kg=10]?\n"
        )
        self.assertEqual(len(res_list), 7)
        q_res = res_list[2]
        self.assertEqual(q_res["statement_type"], "query")
        self.assertEqual(q_res.get("query"), "query what is drone_x?")
        self.assertIsNone(q_res.get("nonexistent_key"))
        self.assertIsInstance(q_res.to_dict(), dict)

    def test_harness_cli_commands(self):
        from ontology_spider.harness.__main__ import main as harness_main

        self.assertEqual(harness_main(["parity", "--model", "examples/tutorial.dialog"]), 0)
        self.assertEqual(harness_main(["run"]), 0)
        self.assertEqual(harness_main(["corpus"]), 0)
        self.assertEqual(harness_main(["bench"]), 0)
        for topo in ["chain", "tree", "lattice", "random_dag", "cyclic"]:
            self.assertEqual(harness_main(["gen", topo, "--size", "6"]), 0)


if __name__ == "__main__":
    unittest.main()
