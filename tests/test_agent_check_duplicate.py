"""Offline unit tests for the agent_check_duplicate.py helper script.

Part of the TDD cycle.
"""

import os
import sys
import json
import unittest
import tempfile
from unittest.mock import patch, MagicMock

# Add project root and scripts directory to python path
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ),
)
sys.path.insert(
    1,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../scripts")
    ),
)


class TestAgentCheckDuplicate(unittest.TestCase):
    """Offline unit test suite for agent_check_duplicate.py."""

    def setUp(self) -> None:
        self._orig_argv = list(sys.argv)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file_path = os.path.join(self.temp_dir.name, "listings.json")
        
        self.dummy_listings = [
            {
                "id": "1",
                "name": "Pinoy Stop Ashfield",
                "facebookUrl": "https://www.facebook.com/pinoystop1",
                "instagramUrl": "https://www.instagram.com/pinoystop",
                "tiktokUrl": None,
                "phone": "+61 2 9797 1234",
                "website": "http://pinoystop.com.au",
                "operatingHours": '{"mon": "9:00 AM - 5:00 PM"}',
                "description": "Authentic Filipino grocery and takeaway in Ashfield.",
                "categories": ["SHOP", "SERVICES"],
                "address": "123 Liverpool Rd, Ashfield",
                "latitude": -33.889,
                "longitude": 151.127,
                "facebookFollowers": 1500,
                "instagramFollowers": 250,
                "tiktokFollowers": None
            },
            {
                "id": "2",
                "name": "Masagana Oriental Variety Store",
                "facebookUrl": None,
                "instagramUrl": None,
                "tiktokUrl": "https://www.tiktok.com/@masagana",
                "phone": None,
                "website": None,
                "operatingHours": None,
                "description": None,
                "categories": ["SHOP"],
                "address": "456 Parramatta Rd, Sydney",
                "latitude": -33.881,
                "longitude": 151.192,
                "facebookFollowers": None,
                "instagramFollowers": None,
                "tiktokFollowers": None
            }
        ]
        with open(self.temp_file_path, "w") as f:
            json.dump(self.dummy_listings, f)

    def tearDown(self) -> None:
        sys.argv = self._orig_argv
        self.temp_dir.cleanup()

    def _extract_json_result(self, mock_stdout: MagicMock) -> dict:
        """Helper to extract the JSON output from stdout calls."""
        for call_args in mock_stdout.write.call_args_list:
            arg = call_args[0][0]
            if '"duplicate"' in arg:
                return json.loads(arg)
        raise AssertionError("No duplicate result JSON found in stdout.")

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_by_url_match(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should detect duplicate if exact social URL exists in DB list."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--url", "https://www.facebook.com/pinoystop1"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["type"], "url")
        self.assertEqual(result["match"]["id"], "1")

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_by_normalized_url_match(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should detect duplicate if social URL matches after normalization."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--url", "http://facebook.com/pinoystop1/"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["type"], "url")

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_by_name_no_url(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should detect duplicate if name matches and candidate has no new URL."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield Pty Ltd."
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["type"], "name")

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_no_duplicate_by_name_with_new_url(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should NOT treat as duplicate if name matches but candidate has a new social URL."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--url", "https://instagram.com/new_ashfield_insta"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_no_duplicate_if_completely_new(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should NOT detect duplicate if both name and URL are completely new."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Completely New Shop",
            "--url", "https://facebook.com/newshop"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_check_with_trace_id(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should accept --trace-id and run successfully."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Completely New Shop",
            "--trace-id", "test-trace-123"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_missing_file_error(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should exit with error if file does not exist."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", "nonexistent_file.json",
            "--name", "Test Shop"
        ]

        with self.assertRaises(SystemExit) as cm:
            agent_check_duplicate.main()
            
        self.assertEqual(cm.exception.code, 1)


    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_no_duplicate_by_name_with_new_website(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should NOT treat as duplicate if name matches but candidate has a new website."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--website", "http://newwebsite.com"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_no_duplicate_by_name_with_new_phone(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should NOT treat as duplicate if name matches but candidate has a new phone number."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--phone", "+61 2 9999 9999"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_no_duplicate_by_name_with_new_hours(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Should NOT treat as duplicate if name matches but candidate has new operating hours."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--hours", '{"mon": "10:00 AM - 6:00 PM"}'
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])


    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_url_duplicate_with_merge_eligible_fields(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """URL-matched duplicate with new fields should return should_merge=True."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--url", "https://www.facebook.com/pinoystop1",
            "--tiktok-url", "https://www.tiktok.com/@pinoystop",
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_identical_data_stays_duplicate(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Candidate with same data already in DB should stay as a true duplicate (no merge)."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--phone", "+61 2 9797 1234",
            "--website", "http://pinoystop.com.au",
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertTrue(result["duplicate"])
        self.assertNotIn("should_merge", result)


    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_new_description_triggers_merge(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate with a different description should trigger should_merge=True."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--description", "Updated description with new info about their catering services.",
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_same_description_stays_duplicate(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate with the same description should stay as a true duplicate."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--description", "Authentic Filipino grocery and takeaway in Ashfield.",
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertTrue(result["duplicate"])
        self.assertNotIn("should_merge", result)

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_different_categories_triggers_merge(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate with different categories should trigger merge (overwrite semantics)."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--categories", "RESTAURANT"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_same_categories_stays_duplicate(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate with identical categories (regardless of order) should not trigger merge."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--categories", "SERVICES,SHOP"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertTrue(result["duplicate"])
        self.assertNotIn("should_merge", result)

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_different_address_triggers_merge(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate with different address should trigger merge."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--address", "999 Liverpool Road, Ashfield NSW"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_different_coordinates_triggers_merge(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate with different latitude/longitude coordinates should trigger merge."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--latitude", "-33.89901",
            "--longitude", "151.12701"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_different_followers_triggers_merge(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate with different follower count should trigger merge."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--name", "Pinoy Stop Ashfield",
            "--facebook-followers", "1501"
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])

    @patch("sys.stdout")
    @patch("sys.stderr")
    def test_duplicate_with_description_fills_empty(self, mock_stderr: MagicMock, mock_stdout: MagicMock) -> None:
        """Duplicate where existing description is empty and candidate has one should trigger merge."""
        import agent_check_duplicate

        sys.argv = [
            "agent_check_duplicate.py",
            "--file", self.temp_file_path,
            "--url", "https://www.tiktok.com/@masagana",
            "--description", "Family-owned Filipino variety store in Sydney.",
        ]

        agent_check_duplicate.main()

        result = self._extract_json_result(mock_stdout)
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["should_merge"])


if __name__ == "__main__":
    unittest.main()
