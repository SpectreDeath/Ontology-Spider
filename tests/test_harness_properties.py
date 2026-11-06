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


if __name__ == "__main__":
    unittest.main()
