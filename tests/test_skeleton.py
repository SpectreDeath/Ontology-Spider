import unittest
import ontology_spider


class TestSkeleton(unittest.TestCase):
    def test_package_version(self):
        self.assertEqual(ontology_spider.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()
