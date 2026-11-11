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
from ontology_spider.prolog.reasoner import PrologReasoner, PrologUnavailableError


class TestDegradedMode(unittest.TestCase):
    def setUp(self):
        self.model = OntologyModel(uri="urn:test:degraded_all")
        p = Provenance(source="test_degraded")
        self.model.add_assertion(Relation("quad", SUBCLASS_OF, "drone"), p)
        self.model.add_assertion(Relation("drone", SUBCLASS_OF, "aircraft"), p)
        self.model.add_assertion(Relation("d1", INSTANCE_OF, "quad"), p, attributes={"payload": 5})
        self.model.add_assertion(Relation("d1", "flies_in", "airspace_1"), p)
        self.model.add_assertion(Relation("airspace_1", "part_of", "region_a"), p)
        self.model.add_entity(Entity(id="d1", attributes={"color": "red"}))

        self.unavailable_reasoner = PrologReasoner(swipl_path="C:\\nonexistent\\swipl.exe")

    def test_degraded_all_queries(self):
        session = DialogSession(
            model=self.model,
            reasoner=self.unavailable_reasoner,
            allow_degraded_fallback=True,
        )

        # 1. Ancestors query
        res_anc = session.run_text("dialog urn:test\nquery ancestors of quad")[0]
        self.assertIn("[Degraded Mode: swipl unavailable]", res_anc.summary_text)
        vals_anc = [a.value for a in res_anc.answers]
        self.assertIn("drone", vals_anc)
        self.assertIn("aircraft", vals_anc)

        # 2. Transitive query
        res_trans = session.run_text("dialog urn:test\nquery transitive part_of from airspace_1")[0]
        self.assertIn("[Degraded Mode: swipl unavailable]", res_trans.summary_text)
        self.assertEqual(len(res_trans.answers), 1)
        self.assertEqual(res_trans.answers[0].value, "region_a")

        # 3. Recommend query
        res_rec = session.run_text("dialog urn:test\nquery recommend drone where payload = 5")[0]
        self.assertIn("[Degraded Mode: swipl unavailable]", res_rec.summary_text)
        self.assertEqual(len(res_rec.answers), 1)
        self.assertEqual(res_rec.answers[0].value, "d1")

        # 4. Pattern query
        res_pat = session.run_text("dialog urn:test\nquery d1 flies_in ?")[0]
        self.assertIn("[Degraded Mode: swipl unavailable]", res_pat.summary_text)
        self.assertEqual(len(res_pat.answers), 1)
        self.assertEqual(res_pat.answers[0].value["object"], "airspace_1")

        # 5. Lookup query
        res_look = session.run_text("dialog urn:test\nquery what is d1?")[0]
        self.assertTrue(len(res_look.answers) >= 1)

    def test_degraded_fallback_disabled_raises(self):
        session = DialogSession(
            model=self.model,
            reasoner=self.unavailable_reasoner,
            allow_degraded_fallback=False,
        )
        with self.assertRaises(PrologUnavailableError):
            session.run_text("dialog urn:test\nquery ancestors of quad")


if __name__ == "__main__":
    unittest.main()
