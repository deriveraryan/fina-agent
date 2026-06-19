"""Unit tests for web_search_tasks._build_task() — maps_formatted_query field.

Tests the pre-computed maps_formatted_query field that replaces 'in' with 'near'
for suburb-level Google Maps Round 4 browser queries to widen the search radius.
"""

import json
import os
import tempfile
import unittest

from features.scanning.web_search_tasks import _build_task, generate_tasks


class TestBuildTaskMapsFormattedQuery(unittest.TestCase):
    """Verify maps_formatted_query field in _build_task() output."""

    def test_city_level_maps_query_equals_formatted_query(self) -> None:
        """City-level tasks: maps_formatted_query should equal formatted_query."""
        task = _build_task(
            city_key="sydney",
            city_display="Sydney",
            category="RESTAURANT",
            template_index=0,
            template="Filipino restaurant in {city}",
            location="Sydney",
            location_type="city",
        )
        self.assertIn("maps_formatted_query", task)
        self.assertEqual(task["maps_formatted_query"], task["formatted_query"])
        self.assertEqual(task["maps_formatted_query"], "Filipino restaurant in Sydney")

    def test_suburb_level_maps_query_swaps_in_to_near(self) -> None:
        """Suburb-level tasks: maps_formatted_query should swap 'in' → 'near'."""
        task = _build_task(
            city_key="sydney",
            city_display="Sydney",
            category="RESTAURANT",
            template_index=0,
            template="Filipino restaurant in {city}",
            location="Parramatta",
            location_type="suburb",
        )
        self.assertIn("maps_formatted_query", task)
        # formatted_query uses "in"
        self.assertEqual(
            task["formatted_query"],
            "Filipino restaurant in Parramatta, Sydney",
        )
        # maps_formatted_query uses "near"
        self.assertEqual(
            task["maps_formatted_query"],
            "Filipino restaurant near Parramatta, Sydney",
        )

    def test_suburb_level_template_without_in_placeholder(self) -> None:
        """Suburb tasks with templates lacking 'in {city}' still produce 'near' maps query.

        Template: 'Balikbayan box {city}' → formatted_query: 'Balikbayan box in Parramatta, Sydney'
        maps_formatted_query should be: 'Balikbayan box near Parramatta, Sydney'
        """
        task = _build_task(
            city_key="sydney",
            city_display="Sydney",
            category="SERVICES",
            template_index=2,
            template="Balikbayan box {city}",
            location="Parramatta",
            location_type="suburb",
        )
        self.assertEqual(
            task["formatted_query"],
            "Balikbayan box in Parramatta, Sydney",
        )
        self.assertEqual(
            task["maps_formatted_query"],
            "Balikbayan box near Parramatta, Sydney",
        )

    def test_city_level_formatted_query_unchanged(self) -> None:
        """Ensure the addition of maps_formatted_query doesn't alter formatted_query."""
        task = _build_task(
            city_key="melbourne",
            city_display="Melbourne",
            category="CAFE",
            template_index=0,
            template="Filipino cafe in {city}",
            location="Melbourne",
            location_type="city",
        )
        self.assertEqual(task["formatted_query"], "Filipino cafe in Melbourne")
        # Verify maps_formatted_query field is also present and correct
        self.assertEqual(task["maps_formatted_query"], "Filipino cafe in Melbourne")

    def test_generate_tasks_suburb_tasks_have_distinct_maps_query(self) -> None:
        """Integration: suburb tasks in generate_tasks() output have maps_formatted_query != formatted_query."""
        # Create minimal fixture files
        categories = {
            "RESTAURANT": {
                "displayName": "Restaurants",
                "searchTemplates": ["Filipino restaurant in {city}"],
            }
        }
        suburbs = {"testcity": ["SuburbA"]}

        with tempfile.TemporaryDirectory() as tmpdir:
            cat_path = os.path.join(tmpdir, "categories.json")
            sub_path = os.path.join(tmpdir, "suburbs.json")
            with open(cat_path, "w") as f:
                json.dump(categories, f)
            with open(sub_path, "w") as f:
                json.dump(suburbs, f)

            tasks = generate_tasks(
                city="testcity",
                categories_path=cat_path,
                suburbs_path=sub_path,
            )

        # Should have 2 tasks: city + suburb
        self.assertEqual(len(tasks), 2)
        city_task = tasks[0]
        suburb_task = tasks[1]

        # City task: maps_formatted_query == formatted_query
        self.assertEqual(
            city_task["maps_formatted_query"],
            city_task["formatted_query"],
        )

        # Suburb task: maps_formatted_query != formatted_query
        self.assertNotEqual(
            suburb_task["maps_formatted_query"],
            suburb_task["formatted_query"],
        )
        self.assertIn("near", suburb_task["maps_formatted_query"])
        self.assertNotIn("near", suburb_task["formatted_query"])


if __name__ == "__main__":
    unittest.main()
