import os
import unittest
import tempfile
import json
from features.scanning.session import (
    load_session_indices,
    save_session_indices,
    get_and_rotate_template,
)


class TestAgentWebFinderSession(unittest.TestCase):
    """Unit tests for the web finder search template rotation and caching logic."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.categories_path = os.path.join(self.temp_dir.name, "categories.json")
        self.session_path = os.path.join(self.temp_dir.name, "web_finder_session.json")

        # Create a mock categories.json structure
        self.mock_categories = {
            "RESTAURANT": {
                "displayName": "Restaurants",
                "searchTemplates": [
                    "Filipino restaurant in {city}",
                    "Filipino food market in {city}",
                    "Filipino food truck in {city}",
                ],
            },
            "CAFE": {
                "displayName": "Cafes",
                "searchTemplates": [
                    "Filipino cafe in {city}",
                ],
            },
        }
        with open(self.categories_path, "w", encoding="utf-8") as f:
            json.dump(self.mock_categories, f)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_load_missing_session_returns_empty_dict(self) -> None:
        """Loading a non-existent session file should return an empty dictionary."""
        data = load_session_indices(self.session_path)
        self.assertEqual(data, {})

    def test_load_corrupt_session_returns_empty_dict(self) -> None:
        """Loading a corrupt or empty session file should return an empty dictionary."""
        with open(self.session_path, "w", encoding="utf-8") as f:
            f.write("{invalid json")
        data = load_session_indices(self.session_path)
        self.assertEqual(data, {})

    def test_first_run_defaults_to_zero_and_saves_index(self) -> None:
        """First run should select index 0, format it, and create/save the index in session JSON."""
        res = get_and_rotate_template(
            city="Sydney",
            category="RESTAURANT",
            categories_path=self.categories_path,
            session_path=self.session_path,
        )

        self.assertEqual(res["index"], 0)
        self.assertEqual(res["template"], "Filipino restaurant in {city}")
        self.assertEqual(res["formatted_query"], "Filipino restaurant in Sydney")
        self.assertEqual(res["total"], 3)

        # Verify saved state on disk
        saved = load_session_indices(self.session_path)
        self.assertEqual(
            saved.get("last_used_template_indices", {}).get("sydney", {}).get("RESTAURANT"),
            0,
        )

    def test_sequential_rotation_and_wraparound(self) -> None:
        """Multiple runs should sequentially advance the index and wrap around via modulo."""
        # 1st run: Index 0
        res1 = get_and_rotate_template(
            city="Sydney",
            category="RESTAURANT",
            categories_path=self.categories_path,
            session_path=self.session_path,
        )
        self.assertEqual(res1["index"], 0)

        # 2nd run: Index 1
        res2 = get_and_rotate_template(
            city="Sydney",
            category="RESTAURANT",
            categories_path=self.categories_path,
            session_path=self.session_path,
        )
        self.assertEqual(res2["index"], 1)
        self.assertEqual(res2["formatted_query"], "Filipino food market in Sydney")

        # 3rd run: Index 2
        res3 = get_and_rotate_template(
            city="Sydney",
            category="RESTAURANT",
            categories_path=self.categories_path,
            session_path=self.session_path,
        )
        self.assertEqual(res3["index"], 2)
        self.assertEqual(res3["formatted_query"], "Filipino food truck in Sydney")

        # 4th run: Index 0 (wraparound)
        res4 = get_and_rotate_template(
            city="Sydney",
            category="RESTAURANT",
            categories_path=self.categories_path,
            session_path=self.session_path,
        )
        self.assertEqual(res4["index"], 0)

    def test_casing_normalization(self) -> None:
        """City keys should be normalized to lowercase, and category keys to uppercase."""
        # Run with uppercase city and mixed category
        get_and_rotate_template(
            city="SYDNEY",
            category="restaurant",
            categories_path=self.categories_path,
            session_path=self.session_path,
        )

        # Verify normalized keys exist in the saved session
        saved = load_session_indices(self.session_path)
        self.assertEqual(
            saved.get("last_used_template_indices", {}).get("sydney", {}).get("RESTAURANT"),
            0,
        )

    def test_out_of_bounds_recovery(self) -> None:
        """If the session contains an out-of-bounds index (e.g. index modified/shrunk), default to 0."""
        # Set an out of bounds index (e.g. 5, but there are only 3 templates)
        initial_session = {
            "last_used_template_indices": {
                "sydney": {
                    "RESTAURANT": 5,
                }
            }
        }
        save_session_indices(self.session_path, initial_session)

        # Run rotation
        res = get_and_rotate_template(
            city="Sydney",
            category="RESTAURANT",
            categories_path=self.categories_path,
            session_path=self.session_path,
        )

        # Should recover and default back to 0
        self.assertEqual(res["index"], 0)
        self.assertEqual(res["formatted_query"], "Filipino restaurant in Sydney")

    def test_invalid_category_raises_value_error(self) -> None:
        """Requesting an undefined category should raise a ValueError."""
        with self.assertRaises(ValueError):
            get_and_rotate_template(
                city="Sydney",
                category="NOT_A_CATEGORY",
                categories_path=self.categories_path,
                session_path=self.session_path,
            )


if __name__ == "__main__":
    unittest.main()
