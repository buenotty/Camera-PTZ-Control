import unittest
from src.utils.updater import UpdateChecker, UpdateCheckThread

class TestUpdater(unittest.TestCase):
    def test_version_comparison(self):
        thread = UpdateCheckThread("1.0.0", "http://dummy")
        # 1.0.1 is newer than 1.0.0
        self.assertTrue(thread._compare_versions("1.0.0", "1.0.1"))
        # 2.0.0 is newer than 1.9.9
        self.assertTrue(thread._compare_versions("1.9.9", "2.0.0"))
        # 1.0.0 is not newer than 1.0.0
        self.assertFalse(thread._compare_versions("1.0.0", "1.0.0"))
        # 1.0.0 is not newer than 1.0.1
        self.assertFalse(thread._compare_versions("1.0.1", "1.0.0"))

    def test_version_comparison_with_v_prefix(self):
        thread = UpdateCheckThread("1.0.0", "http://dummy")
        self.assertTrue(thread._compare_versions("1.0.0", "v1.1.0".lstrip("v")))

if __name__ == '__main__':
    unittest.main()
