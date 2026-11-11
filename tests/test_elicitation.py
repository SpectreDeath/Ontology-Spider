import unittest

from ontology_spider.elicitation import ElicitationManager
from ontology_spider.model import DISJOINT_WITH, SUBCLASS_OF


class TestElicitation(unittest.TestCase):
    def test_scripted_elicitation_session(self):
        manager = ElicitationManager(uri="urn:test:elicited")
        # 1. Start -> Decision Question
        prompt = manager.start()
        self.assertIn("Decision Question", prompt)

        # 2. Scope Answer
        prompt = manager.step("Medical device taxonomy")
        self.assertIn("competency question", prompt.lower())

        # 3. Add Competency Question
        prompt = manager.step("query ancestors of pacemaker")
        self.assertIn("Competency query recorded", prompt)
        prompt = manager.step("done")
        self.assertIn("class hierarchies", prompt)

        # 4. Elicit Class
        prompt = manager.step("cardiac_implant subclass_of medical_device")
        self.assertIn("Please confirm", prompt)

        # 5. Confirm Class
        prompt = manager.step("y")
        self.assertIn("Confirmed", prompt)
        prompt = manager.step("done")
        self.assertIn("relation constraints", prompt)

        # 6. Elicit Relation
        prompt = manager.step("implanted_in domain=device range=organ")
        self.assertIn("Please confirm", prompt)
        prompt = manager.step("y")
        self.assertIn("Confirmed", prompt)
        prompt = manager.step("done")
        self.assertIn("instances", prompt)

        # 7. Elicit Instance
        prompt = manager.step("pacemaker instance_of cardiac_implant")
        self.assertIn("Please confirm", prompt)
        prompt = manager.step("y")
        self.assertIn("Confirmed", prompt)
        prompt = manager.step("done")
        self.assertIn("Elicitation completed", prompt)

        # Verify model content
        self.assertEqual(len(manager.model.assertions), 4)
        subclass_asrt = manager.model.query(predicate=SUBCLASS_OF)
        self.assertEqual(len(subclass_asrt), 1)
        self.assertEqual(subclass_asrt[0].relation.subject, "cardiac_implant")

        # Run recorded competency questions
        comp_results = manager.run_competency_queries()
        self.assertEqual(len(comp_results), 1)
        self.assertTrue(comp_results[0]["passed"])
        self.assertIn("medical_device", comp_results[0]["answers"])

    def test_unconfirmed_assertions_never_reach_model(self):
        manager = ElicitationManager()
        manager.start()
        manager.step("Testing rejection")
        manager.step("done")  # Skip competency
        # Elicit class
        manager.step("cat subclass_of mammal")
        # Reject confirmation
        manager.step("n")
        manager.step("done")  # Skip classes
        manager.step("done")  # Skip relations
        manager.step("done")  # Skip instances

        # Model should have zero assertions
        self.assertEqual(len(manager.model.assertions), 0)

    def test_mixed_initiative_amendment(self):
        manager = ElicitationManager()
        manager.start()
        manager.step("Pet ontology")
        manager.step("done")

        # Turn: dog subclass_of pet
        manager.step("dog subclass_of pet")
        manager.step("y")
        turn_to_amend = manager.turns[-1].turn_id

        # Turn: fido instance_of dog
        manager.step("done")  # Skip classes
        manager.step("done")  # Skip relations
        manager.step("fido instance_of dog")
        manager.step("y")
        manager.step("done")  # Complete

        self.assertEqual(len(manager.model.assertions), 2)

        # Amend turn_to_amend
        amend_msg = manager.amend_turn(turn_to_amend, "canine subclass_of pet")
        self.assertIn("retracted", amend_msg.lower())

        # Assertions from that turn must be retracted
        remaining = manager.model.query(subject="dog")
        self.assertEqual(len(remaining), 0)
        # New assertion should be present
        canine_asrt = manager.model.query(subject="canine")
        self.assertEqual(len(canine_asrt), 1)

    def test_disjoint_and_attributes_and_dependency_tracking(self):
        manager = ElicitationManager()
        manager.start()
        manager.step("Robotics")
        manager.step("done")

        # Class 1: aerial_robot subclass_of robot
        manager.step("aerial_robot subclass_of robot")
        manager.step("y")
        turn_class1 = manager.turns[-1].turn_id

        # Class 2: ground_robot subclass_of robot
        manager.step("ground_robot subclass_of robot")
        manager.step("y")
        turn_class2 = manager.turns[-1].turn_id

        # Class 3: aerial_robot disjoint_with ground_robot
        manager.step("aerial_robot disjoint_with ground_robot")
        manager.step("y")
        turn_disjoint = manager.turns[-1]
        self.assertIn(turn_class1, turn_disjoint.depends_on_turn_ids)
        self.assertIn(turn_class2, turn_disjoint.depends_on_turn_ids)

        manager.step("done")  # Skip classes

        # Relation: flies_in domain=aerial_robot range=airspace acyclic=true
        manager.step("flies_in domain=aerial_robot range=airspace acyclic=true")
        manager.step("y")
        turn_rel = manager.turns[-1]
        self.assertIn(turn_class1, turn_rel.depends_on_turn_ids)

        manager.step("done")  # Skip relations

        # Instance: drone1 instance_of aerial_robot [payload_kg=5, max_speed=40]
        manager.step("drone1 instance_of aerial_robot [payload_kg=5, max_speed=40]")
        manager.step("y")
        turn_inst = manager.turns[-1]
        self.assertIn(turn_class1, turn_inst.depends_on_turn_ids)

        # Verify entity attributes
        drone_ent = manager.model.get_entity("drone1")
        self.assertIsNotNone(drone_ent)
        self.assertEqual(drone_ent.attributes.get("payload_kg"), 5)
        self.assertEqual(drone_ent.attributes.get("max_speed"), 40)

        # Verify disjoint assertion exists
        disj = manager.model.query(predicate=DISJOINT_WITH)
        self.assertEqual(len(disj), 1)
        self.assertEqual(disj[0].relation.subject, "aerial_robot")
        self.assertEqual(disj[0].relation.object, "ground_robot")

    def test_full_amendment_with_downstream_reconfirmation(self):
        manager = ElicitationManager()
        manager.start()
        manager.step("Aviation")
        manager.step("done")

        # Class: drone subclass_of aircraft
        manager.step("drone subclass_of aircraft")
        manager.step("y")
        turn_class = manager.turns[-1].turn_id

        manager.step("done")  # to relations
        manager.step("done")  # to instances

        # Instance: sky_scout instance_of drone [range_km=100]
        manager.step("sky_scout instance_of drone [range_km=100]")
        manager.step("y")
        turn_inst = manager.turns[-1].turn_id

        self.assertEqual(len(manager.model.assertions), 2)

        # Amend class turn
        amend_msg = manager.amend_turn(turn_class, "uav subclass_of aircraft")
        self.assertIn("re-confirmation required", amend_msg.lower())
        self.assertEqual(len(manager.pending_reconfirmations), 1)

        # sky_scout should be retracted
        self.assertEqual(len(manager.model.query(subject="sky_scout")), 0)
        # uav should be present
        self.assertEqual(len(manager.model.query(subject="uav")), 1)

        # Confirm the downstream turn
        prompt = manager.step("y")
        self.assertIn("Re-confirmed turn", prompt)
        self.assertEqual(len(manager.pending_reconfirmations), 0)
        self.assertEqual(len(manager.model.query(subject="sky_scout")), 1)

    def test_amend_relations_and_instances_and_rejections(self):
        manager = ElicitationManager()
        self.assertIn("Decision Question", manager.prompt())
        manager.handle_input("Testing Coverage")
        manager.handle_input("query ancestors of initial_entity")
        manager.handle_input("done")

        # Invalid class format
        inv_cls = manager.handle_input("just_one_token")
        self.assertIn("Invalid class format", inv_cls)

        # Class: vehicle subclass_of entity
        manager.handle_input("vehicle subclass_of entity")
        manager.handle_input("y")
        manager.handle_input("done")

        # Invalid relation
        inv_rel = manager.handle_input("has_engine invalid_param")
        self.assertIn("No valid", inv_rel)

        # Valid relation
        manager.handle_input("drives domain=person range=vehicle acyclic=true")
        manager.handle_input("y")
        rel_turn_id = manager.turns[-1].turn_id

        # Amend relation turn
        amend_rel = manager.amend_turn(rel_turn_id, "operates domain=operator range=vehicle acyclic=true")
        self.assertIn("retracted", amend_rel.lower())

        manager.handle_input("done")  # Skip to instances

        # Invalid instance
        inv_inst = manager.handle_input("single_token_inst")
        self.assertIn("Invalid instance", inv_inst)

        # Instance turn
        manager.handle_input("truck1 instance_of vehicle [wheels=6]")
        manager.handle_input("y")
        inst_turn_id = manager.turns[-1].turn_id

        # Amend instance turn
        amend_inst = manager.amend_turn(inst_turn_id, "truck1 instance_of vehicle [wheels=8]")
        self.assertIn("truck1 instance_of vehicle", amend_inst)

        # Downstream rejection in amendment
        manager.handle_input("truck1 instance_of vehicle")
        # Reject confirmation
        manager.handle_input("n")
        self.assertIn("discarded", manager.prompt().lower())

        # Amend decision and competency questions
        dec_turn_id = manager.turns[0].turn_id
        res_dec = manager.amend_turn(dec_turn_id, "Updated Coverage Domain")
        self.assertIn("Updated scope", res_dec)
        self.assertEqual(manager.scope_description, "Updated Coverage Domain")

        comp_turn_id = manager.turns[1].turn_id
        res_comp = manager.amend_turn(comp_turn_id, "query ancestors of truck1")
        self.assertIn("Updated competency question", res_comp)
        self.assertIn("query ancestors of truck1", manager.competency_queries)

        # Finish
        final = manager.handle_input("done")
        self.assertIn("Elicitation completed", final)

    def test_amend_instance_with_downstream_dependency(self):
        """Amending an instance assertion should retract its assertion and invalidate downstream turns using that symbol."""
        manager = ElicitationManager()
        manager.start()
        manager.step("Robotics")
        manager.step("done")  # Skip competency
        manager.step("done")  # Skip classes
        manager.step("done")  # Skip relations

        # Step 1: drone1 instance_of quadcopter
        manager.step("drone1 instance_of quadcopter")
        manager.step("y")
        turn_inst1 = manager.turns[-1].turn_id

        # Step 2: drone1 carries payload1
        manager.step("drone1 carries payload1")
        manager.step("y")
        turn_inst2 = manager.turns[-1].turn_id

        # Assertions present
        self.assertEqual(len(manager.model.query(subject="drone1")), 2)

        # Amend turn_inst1
        amend_msg = manager.amend_turn(turn_inst1, "drone1 instance_of heavy_lifter [max_kg=50]")
        self.assertIn("retracted", amend_msg.lower())
        self.assertIn("re-confirmation required", amend_msg.lower())
        self.assertEqual(len(manager.pending_reconfirmations), 1)
        self.assertEqual(manager.pending_reconfirmations[0].turn_id, turn_inst2)

        # Reconfirm downstream turn
        conf_prompt = manager.handle_input("y")
        self.assertIn("re-confirmed", conf_prompt.lower())
        self.assertEqual(len(manager.pending_reconfirmations), 0)


if __name__ == "__main__":
    unittest.main()
