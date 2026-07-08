import unittest
import json
import os
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import app

class TestServerAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        # Set up a real temporary profile file in the output folder for list/get/delete tests
        self.temp_username = "temp_test_user"
        self.outdir = Path("output")
        self.outdir.mkdir(parents=True, exist_ok=True)
        
        self.temp_json_path = self.outdir / f"{self.temp_username}_profile.json"
        self.temp_md_path = self.outdir / f"{self.temp_username}_profile.md"
        
        self.mock_profile_data = {
            "about": {
                "name": self.temp_username,
                "created_utc": 1500000000,
                "link_karma": 50,
                "comment_karma": 150,
                "total_karma": 200,
                "is_mod": False
            },
            "counts": {
                "posts": 5,
                "comments": 15,
                "total": 20,
                "valid_posts": 5,
                "valid_comments": 15,
                "valid_total": 20
            },
            "tz_estimate_combined": {
                "quiet_window_utc": "01:00-07:00",
                "estimated_utc_offset": 3,
                "confidence_heuristic": "medium",
                "note": "Test note"
            },
            "posts_raw": [],
            "comments_raw": [],
            "unique_subreddits_combined": 2,
            "status": "success",
            "queried_username": self.temp_username
        }
        
        # Write files
        self.temp_json_path.write_text(json.dumps(self.mock_profile_data), encoding="utf-8")
        self.temp_md_path.write_text("# Mock Profile markdown content", encoding="utf-8")

    def tearDown(self):
        # Clean up files if they still exist
        if self.temp_json_path.exists():
            self.temp_json_path.unlink()
        if self.temp_md_path.exists():
            self.temp_md_path.unlink()

    def test_invalid_username_length(self):
        response = self.client.get("/api/analyse?username=ab")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid or unsafe username", response.json()["detail"])

        response = self.client.get("/api/analyse?username=" + ("a" * 21))
        self.assertEqual(response.status_code, 400)

    def test_invalid_username_characters(self):
        response = self.client.get("/api/analyse?username=user.name")
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/analyse?username=user/path")
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/analyse?username=user%20name")
        self.assertEqual(response.status_code, 400)

    @patch("app.fetch_about")
    @patch("app.fetch_listing")
    def test_analyse_success_flow(self, mock_fetch_listing, mock_fetch_about):
        # Setup mocks for live profiling
        mock_fetch_about.return_value = {
            "name": "live_test_user",
            "created_utc": 1600000000,
            "link_karma": 100,
            "comment_karma": 200,
            "total_karma": 300,
            "is_mod": False,
        }
        
        mock_fetch_listing.side_effect = [
            # submitted posts
            [
                {
                    "name": "t3_p1",
                    "subreddit": "python",
                    "score": 10,
                    "title": "Mock submission title",
                    "selftext": "Mock submission body",
                    "created_utc": 1600003600,
                    "permalink": "/r/python/comments/p1",
                    "fetched_from": "reddit"
                }
            ],
            # comments
            [
                {
                    "name": "t1_c1",
                    "subreddit": "python",
                    "score": 5,
                    "body": "Mock comment body",
                    "created_utc": 1600007200,
                    "permalink": "/r/python/comments/p1/c1",
                    "fetched_from": "reddit"
                }
            ]
        ]

        response = self.client.get("/api/analyse?username=live_test_user&limit=10&source=reddit")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["queried_username"], "live_test_user")
        self.assertEqual(data["counts"]["posts"], 1)
        self.assertEqual(data["counts"]["comments"], 1)
        self.assertEqual(data["counts"]["total"], 2)
        
        # Verify that output files were automatically created
        live_json_path = self.outdir / "live_test_user_profile.json"
        live_md_path = self.outdir / "live_test_user_profile.md"
        self.assertTrue(live_json_path.exists())
        self.assertTrue(live_md_path.exists())
        
        # Clean up
        live_json_path.unlink()
        live_md_path.unlink()

    @patch("app.fetch_about")
    @patch("app.fetch_listing")
    def test_analyse_no_data_found(self, mock_fetch_listing, mock_fetch_about):
        mock_fetch_about.return_value = None
        mock_fetch_listing.return_value = []

        response = self.client.get("/api/analyse?username=nonexistent")
        self.assertEqual(response.status_code, 404)
        self.assertIn("No public data or metadata found", response.json()["detail"])

    def test_list_saved_profiles(self):
        response = self.client.get("/api/profiles")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIsInstance(data, list)
        
        # Check that our temp profile exists in list
        temp_profiles = [p for p in data if p["username"] == self.temp_username]
        self.assertEqual(len(temp_profiles), 1)
        
        p = temp_profiles[0]
        self.assertEqual(p["total"], 20)
        self.assertEqual(p["posts"], 5)
        self.assertEqual(p["comments"], 15)
        self.assertEqual(p["total_karma"], 200)
        self.assertEqual(p["utc_offset"], 3)
        self.assertEqual(p["confidence"], "medium")

    def test_get_saved_profile_success(self):
        response = self.client.get(f"/api/profiles/{self.temp_username}")
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data["queried_username"], self.temp_username)
        self.assertEqual(data["counts"]["total"], 20)

    def test_get_saved_profile_not_found(self):
        response = self.client.get("/api/profiles/some_missing_user")
        self.assertEqual(response.status_code, 404)
        self.assertIn("was not found in the output folder", response.json()["detail"])

    def test_delete_saved_profile_success(self):
        # Verify files exist first
        self.assertTrue(self.temp_json_path.exists())
        self.assertTrue(self.temp_md_path.exists())
        
        response = self.client.delete(f"/api/profiles/{self.temp_username}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        
        # Verify files are deleted
        self.assertFalse(self.temp_json_path.exists())
        self.assertFalse(self.temp_md_path.exists())

    def test_delete_saved_profile_not_found(self):
        response = self.client.delete("/api/profiles/some_missing_user")
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
