import unittest

from ontology_spider.elicitation import ElicitationManager, ElicitationState
from ontology_spider.model import SUBCLASS_OF, INSTANCE_OF


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


if __name__ == "__main__":
    unittest.main()
