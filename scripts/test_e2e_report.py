import unittest

from check_e2e_report import complete


class BrowserAcceptanceTest(unittest.TestCase):
    def test_requires_passing_tests_without_omissions(self):
        stats = {"expected": 2, "unexpected": 0, "flaky": 0, "skipped": 0}
        self.assertTrue(complete({"stats": stats}))
        for field in ("unexpected", "flaky", "skipped"):
            self.assertFalse(complete({"stats": {**stats, field: 1}}))
        self.assertFalse(complete({"stats": {**stats, "expected": 0}}))
        self.assertFalse(complete({"stats": stats, "errors": [{"message": "crash"}]}))
        self.assertFalse(complete({}))


if __name__ == "__main__":
    unittest.main()
