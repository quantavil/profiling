import unittest
from profiling.analyzer import score_stats, estimate_tz, analyse

class TestAnalyzer(unittest.TestCase):
    def test_score_stats(self):
        self.assertEqual(score_stats([]), {})
        self.assertEqual(score_stats([{"score": 10}, {"score": 20}]), {
            "total": 30,
            "mean": 15.0,
            "median": 15.0,
            "max": 20,
            "min": 10
        })

    def test_estimate_tz(self):
        # Active mostly except 02:00 to 08:00 UTC (sleep window)
        hour_totals = [10] * 24
        for hour in range(2, 8):
            hour_totals[hour] = 0
        tz = estimate_tz(hour_totals)
        self.assertIsNotNone(tz)
        self.assertEqual(tz["quiet_window_utc"], "02:00-08:00")
        # sleep mid is 2 + 3 = 5 UTC. Offset = 3 - 5 = -2.
        self.assertEqual(tz["estimated_utc_offset"], -2)

    def test_analyse_deleted_content(self):
        # Verify that deleted posts/comments are included in counts and heatmaps but skipped in word counts
        posts = [
            {
                "name": "t3_p1",
                "subreddit": "python",
                "score": 10,
                "title": "Legitimate python post",
                "selftext": "some content here",
                "created_utc": 1600000000,
            },
            {
                "name": "t3_p2",
                "subreddit": "python",
                "score": 5,
                "title": "[deleted]",
                "selftext": "[deleted]",
                "created_utc": 1600003600,
            }
        ]
        comments = [
            {
                "name": "t1_c1",
                "subreddit": "test",
                "score": 2,
                "body": "Legitimate comment text",
                "created_utc": 1600007200,
            }
        ]
        res = analyse(None, posts, comments)
        self.assertEqual(res["counts"]["posts"], 2)
        self.assertEqual(res["counts"]["comments"], 1)
        self.assertEqual(res["counts"]["valid_posts"], 1)
        self.assertEqual(res["counts"]["valid_comments"], 1)
        
        # Word counters should skip "[deleted]"
        keywords_posts = dict(res["top_keywords_posts"])
        self.assertIn("legitimate", keywords_posts)
        self.assertNotIn("[deleted]", keywords_posts)
        self.assertNotIn("deleted", keywords_posts)

if __name__ == "__main__":
    unittest.main()
