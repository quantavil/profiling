import unittest
from profiling.utils import parse_reddit_score, escape_markdown, is_deleted_or_removed, _get_fullname

class TestUtils(unittest.TestCase):
    def test_parse_reddit_score(self):
        self.assertEqual(parse_reddit_score("1,234 points"), 1234)
        self.assertEqual(parse_reddit_score("-5 downvotes"), -5)
        self.assertEqual(parse_reddit_score("•"), 0)
        self.assertEqual(parse_reddit_score("hidden score"), 0)
        self.assertEqual(parse_reddit_score("15.5k"), 15500)
        self.assertEqual(parse_reddit_score("1.2m"), 1200000)
        self.assertEqual(parse_reddit_score(""), 0)
        self.assertEqual(parse_reddit_score(None), 0)

    def test_escape_markdown(self):
        self.assertEqual(escape_markdown("Hello *world*"), "Hello \\*world\\*")
        self.assertEqual(escape_markdown(""), "")
        self.assertEqual(escape_markdown(None), "")

    def test_is_deleted_or_removed(self):
        self.assertTrue(is_deleted_or_removed({"selftext": "[deleted]"}))
        self.assertTrue(is_deleted_or_removed({"body": "[removed]"}))
        self.assertTrue(is_deleted_or_removed({"author": "[deleted]"}))
        self.assertFalse(is_deleted_or_removed({"selftext": "deleted but not bracketed"}))
        self.assertFalse(is_deleted_or_removed({"body": "my comment got removed"}))

    def test_get_fullname(self):
        self.assertEqual(_get_fullname({"name": "t1_abc"}, "comments"), "t1_abc")
        self.assertEqual(_get_fullname({"id": "abc"}, "comments"), "t1_abc")
        self.assertEqual(_get_fullname({"id": "t3_abc"}, "submitted"), "t3_abc")
        self.assertEqual(_get_fullname({"id": "abc"}, "submitted"), "t3_abc")
        self.assertIsNone(_get_fullname({}, "comments"))

if __name__ == "__main__":
    unittest.main()
