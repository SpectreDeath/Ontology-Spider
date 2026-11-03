import unittest

from ontology_spider.elicitation import ElicitationManager
from ontology_spider.model import (
    ACYCLIC,
    DISJOINT_WITH,
    DOMAIN,
    INSTANCE_OF,
    RANGE,
    SUBCLASS_OF,
    OntologyModel,
    Provenance,
    Relation,
)
from ontology_spider.validation import OntologyValidator, validate_model_hook


class TestValidation(unittest.TestCase):
    def setUp(self):
        self.validator = OntologyValidator()

    def test_domain_violation(self):
        model = OntologyModel(uri="urn:test:domain")
        p = Provenance(source="test")
        # eats has domain animal
        d_asrt = model.add_assertion(Relation("eats", DOMAIN, "animal"), p)
        # rock eats moss -> rock is not an animal
        r_asrt = model.add_assertion(Relation("rock", "eats", "moss"), p)

        violations = self.validator.validate(model)
        dom_viols = [v for v in violations if v.check_type == "domain_violation"]
        self.assertEqual(len(dom_viols), 1)
        self.assertIn(r_asrt.assertion_id, dom_viols[0].offending_assertion_ids)
        self.assertIn(d_asrt.assertion_id, dom_viols[0].offending_assertion_ids)

    def test_range_violation(self):
        model = OntologyModel(uri="urn:test:range")
        p = Provenance(source="test")
        # author_of has range book
        r_decl = model.add_assertion(Relation("author_of", RANGE, "book"), p)
        # alice author_of movie -> movie is not book
        u_asrt = model.add_assertion(Relation("alice", "author_of", "movie"), p)

        violations = self.validator.validate(model)
        rng_viols = [v for v in violations if v.check_type == "range_violation"]
        self.assertEqual(len(rng_viols), 1)
        self.assertIn(u_asrt.assertion_id, rng_viols[0].offending_assertion_ids)

    def test_disjointness_violation(self):
        model = OntologyModel(uri="urn:test:disjoint")
        p = Provenance(source="test")
        # carnivore disjoint_with herbivore
        dis_asrt = model.add_assertion(Relation("carnivore", DISJOINT_WITH, "herbivore"), p)
        # felix instance_of carnivore AND herbivore
        i1 = model.add_assertion(Relation("felix", INSTANCE_OF, "carnivore"), p)
        i2 = model.add_assertion(Relation("felix", INSTANCE_OF, "herbivore"), p)

        violations = self.validator.validate(model)
        dis_viols = [v for v in violations if v.check_type == "disjointness_violation"]
        self.assertEqual(len(dis_viols), 1)
        self.assertIn(dis_asrt.assertion_id, dis_viols[0].offending_assertion_ids)
        self.assertIn(i1.assertion_id, dis_viols[0].offending_assertion_ids)

    def test_acyclic_violation(self):
        model = OntologyModel(uri="urn:test:acyclic")
        p = Provenance(source="test")
        # part_of is acyclic
        model.add_assertion(Relation("part_of", ACYCLIC, "true"), p)
        # Cycle: a part_of b, b part_of c, c part_of a
        a1 = model.add_assertion(Relation("a", "part_of", "b"), p)
        a2 = model.add_assertion(Relation("b", "part_of", "c"), p)
        a3 = model.add_assertion(Relation("c", "part_of", "a"), p)

        violations = self.validator.validate(model)
        cyc_viols = [v for v in violations if v.check_type == "cycle_violation"]
        self.assertEqual(len(cyc_viols), 1)
        self.assertTrue(len(cyc_viols[0].offending_assertion_ids) >= 2)

    def test_clean_model_passes_without_violations(self):
        model = OntologyModel(uri="urn:test:clean")
        p = Provenance(source="test")
        model.add_assertion(Relation("dog", SUBCLASS_OF, "mammal"), p)
        model.add_assertion(Relation("fido", INSTANCE_OF, "dog"), p)

        # Custom validator with only core constraints (no optional missing domain/range warnings)
        clean_validator = OntologyValidator(custom_assumptions=[])
        # Filter for strict constraint violations
        violations = [
            v for v in clean_validator.validate(model)
            if v.check_type in ("domain_violation", "range_violation", "disjointness_violation", "cycle_violation")
        ]
        self.assertEqual(len(violations), 0)

    def test_validation_hook_in_elicitation(self):
        manager = ElicitationManager(validation_hook=validate_model_hook)
        manager.start()
        manager.step("Medical devices")
        manager.step("done")
        manager.step("done")
        manager.step("done")
        manager.step("done")  # Finishes elicitation
        summary = manager._finalize_elicitation()
        self.assertIn("Model integrity checks", summary)


if __name__ == "__main__":
    unittest.main()
