import unittest

from ontology_spider.dialog_runner import DialogSession
from ontology_spider.model import (
    INSTANCE_OF,
    SUBCLASS_OF,
    Entity,
    OntologyModel,
    Provenance,
    Relation,
)
from ontology_spider.traversal import TraversalDialogueManager


class TestTraversalDialogue(unittest.TestCase):
    def setUp(self):
        self.model = OntologyModel(uri="urn:test:traversal")
        prov = Provenance(source="test_traversal")
        self.model.add_assertion(Relation("electric_car", SUBCLASS_OF, "car"), prov)
        self.model.add_assertion(Relation("car", SUBCLASS_OF, "vehicle"), prov)
        self.model.add_assertion(Relation("leaf", INSTANCE_OF, "electric_car"), prov)
        self.model.add_assertion(Relation("leaf", "range_km", "250"), prov)

        # Register entity attributes
        self.model.add_entity(Entity(id="leaf", attributes={"fuel": "electric"}))
        self.model.add_entity(Entity(id="prius", attributes={"fuel": "hybrid"}))

    def test_frame_stack_and_where_am_i(self):
        manager = TraversalDialogueManager(model=self.model)
        status_init = manager.where_am_i()
        self.assertIn("1 frames active", status_init)

        # Focus on leaf
        msg = manager.set_focus("leaf", {"fuel": "electric"})
        self.assertIn("Focused on entity 'leaf'", msg)

        status_focused = manager.where_am_i()
        self.assertIn("2 frames active", status_focused)
        self.assertIn("focus='leaf'", status_focused)

    def test_query_and_explanation_in_frame(self):
        manager = TraversalDialogueManager(model=self.model)
        manager.set_focus("leaf")

        # Query ancestors using focus
        res = manager.query("query ancestors of leaf")
        self.assertEqual(res.statement_type, "query")
        values = [str(a.value) for a in res.answers]
        self.assertIn("electric_car", values)
        self.assertIn("car", values)
        self.assertIn("vehicle", values)

        # Explain follow-up
        exp_text = manager.explain()
        self.assertIn("Explanation", exp_text)
        self.assertTrue(
            "ancestor_rule" in exp_text or "degraded_python_fallback" in exp_text,
            f"Expected ancestor_rule or degraded_python_fallback in: {exp_text}",
        )

    def test_constraint_change_aborts_conflicting_subframe(self):
        manager = TraversalDialogueManager(model=self.model)
        # Push subframe for leaf (fuel=electric)
        manager.set_focus("leaf", {"fuel": "electric"})
        self.assertEqual(len(manager.frame_stack), 2)

        # Change constraint to fuel=hybrid -> leaf conflicts, so subframe must be aborted/popped!
        update_msg = manager.change_constraint("fuel", "hybrid")
        self.assertIn("Aborted conflicting subdialogue frames", update_msg)
        self.assertEqual(len(manager.frame_stack), 1)
        self.assertEqual(manager.current_frame.active_constraints.get("fuel"), "hybrid")

    def test_batch_and_traversal_parity(self):
        # Query via batch session
        batch_session = DialogSession(model=self.model)
        batch_res = batch_session.run_text("query ancestors of leaf")[0]

        # Query via traversal manager
        trav_manager = TraversalDialogueManager(model=self.model)
        trav_res = trav_manager.query("query ancestors of leaf")

        self.assertEqual(len(batch_res.answers), len(trav_res.answers))
        self.assertEqual(
            [a.value for a in batch_res.answers],
            [a.value for a in trav_res.answers],
        )

    def test_frame_constraint_filtering_and_recommend(self):
        manager = TraversalDialogueManager(model=self.model)
        # Register a second electric car with different range
        prov = Provenance(source="test_traversal")
        self.model.add_assertion(Relation("bolt", INSTANCE_OF, "electric_car"), prov)
        self.model.add_entity(Entity(id="bolt", attributes={"fuel": "electric", "range_km": 380}))
        self.model.upsert_entity("leaf", range_km=250)

        # Change constraint range_km=380 in root frame
        manager.change_constraint("range_km", "380")

        # Recommend electric_car
        res = manager.query("query recommend electric_car")
        self.assertEqual(len(res.answers), 1)
        self.assertEqual(res.answers[0].value, "bolt")
        self.assertIn("filtered_by_frame_constraints", res.answers[0].explanation.rules_fired)

    def test_multi_constraint_post_filter_enforces_all_constraints(self):
        # D8 proof: traversal post-filter at traversal.py:145 enforces ALL active frame constraints
        manager = TraversalDialogueManager(model=self.model)
        prov = Provenance(source="test_d8")
        self.model.add_assertion(Relation("car_a", INSTANCE_OF, "electric_car"), prov)
        self.model.add_assertion(Relation("car_b", INSTANCE_OF, "electric_car"), prov)
        self.model.add_assertion(Relation("car_c", INSTANCE_OF, "electric_car"), prov)

        self.model.upsert_entity("car_a", fuel="electric", seats="4", color="red")
        self.model.upsert_entity("car_b", fuel="electric", seats="4", color="blue")
        self.model.upsert_entity("car_c", fuel="electric", seats="2", color="red")

        manager.change_constraint("seats", "4")
        manager.change_constraint("color", "red")

        # Both seats=4 AND color=red must be satisfied -> only car_a matches
        res = manager.query("query recommend electric_car")
        self.assertEqual(len(res.answers), 1)
        self.assertEqual(res.answers[0].value, "car_a")
        self.assertIn("filtered_by_frame_constraints", res.answers[0].explanation.rules_fired)

    def test_inline_explain_execution(self):
        manager = TraversalDialogueManager(model=self.model)
        res = manager.query("explain query ancestors of leaf")
        self.assertEqual(res.statement_type, "explain")
        self.assertIn("Answer #", res.summary_text)
        self.assertIn("electric_car", res.summary_text)


if __name__ == "__main__":
    unittest.main()
