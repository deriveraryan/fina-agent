"""Unit tests for web_search_tasks._build_task() — maps_formatted_query field.

Tests the pre-computed maps_formatted_query field that replaces 'in' with 'near'
for suburb-level Google Maps Round 4 browser queries to widen the search radius.
"""

import json
import os
import shutil
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


class TestCityFirstTaskOrdering(unittest.TestCase):
    """Verify that all city-level tasks are ordered before all suburb-level tasks."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir)
        self.categories_path = os.path.join(self.tmpdir, "categories.json")
        self.suburbs_path = os.path.join(self.tmpdir, "suburbs.json")

        # Two categories, each with one template, two suburbs
        categories = {
            "RESTAURANT": {
                "displayName": "Restaurants",
                "searchTemplates": ["Filipino restaurant in {city}"],
            },
            "SERVICES": {
                "displayName": "Services",
                "searchTemplates": ["Filipino services in {city}"],
            },
        }
        suburbs = {"sydney": ["Parramatta", "Blacktown"]}

        with open(self.categories_path, "w") as f:
            json.dump(categories, f)
        with open(self.suburbs_path, "w") as f:
            json.dump(suburbs, f)

    def test_city_tasks_ordered_before_suburb_tasks(self) -> None:
        """ALL city-level tasks must appear before ANY suburb-level task.

        With 2 categories × 1 template × (1 city + 2 suburbs) = 6 tasks total.
        Expected order: 2 city tasks first, then 4 suburb tasks.
        """
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(len(tasks), 6)

        location_types = [t["location_type"] for t in tasks]
        # All city tasks first, then all suburb tasks
        city_count = location_types.count("city")
        self.assertEqual(city_count, 2)
        self.assertEqual(location_types[:2], ["city", "city"])
        self.assertTrue(all(lt == "suburb" for lt in location_types[2:]))

        # City tasks should still be in category order
        self.assertEqual(tasks[0]["category"], "RESTAURANT")
        self.assertEqual(tasks[1]["category"], "SERVICES")


class TestCityOnlyTemplateIndices(unittest.TestCase):
    """Verify the cityOnlySearchTemplateIndices feature."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir)
        self.categories_path = os.path.join(self.tmpdir, "categories.json")
        self.suburbs_path = os.path.join(self.tmpdir, "suburbs.json")

        suburbs = {"sydney": ["Parramatta"]}
        with open(self.suburbs_path, "w") as f:
            json.dump(suburbs, f)

    def _write_categories(self, data: dict) -> None:
        with open(self.categories_path, "w") as f:
            json.dump(data, f)

    def test_city_only_template_indices_skips_suburb_tasks(self) -> None:
        """Templates listed in cityOnlySearchTemplateIndices should produce only city-level tasks.

        Category has 2 templates; template index 1 is city-only.
        Expected: template 0 → city + suburb (2), template 1 → city only (1) = 3 total.
        """
        self._write_categories({
            "RESTAURANT": {
                "displayName": "Restaurants",
                "searchTemplates": [
                    "Filipino restaurant in {city}",
                    "Pinoy eatery in {city}",
                ],
                "cityOnlySearchTemplateIndices": [1],
            },
        })
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(len(tasks), 3)

        # Template 0: city + suburb
        t0_tasks = [t for t in tasks if t["template_index"] == 0]
        self.assertEqual(len(t0_tasks), 2)
        self.assertEqual(
            sorted([t["location_type"] for t in t0_tasks]),
            ["city", "suburb"],
        )

        # Template 1: city only (no suburb)
        t1_tasks = [t for t in tasks if t["template_index"] == 1]
        self.assertEqual(len(t1_tasks), 1)
        self.assertEqual(t1_tasks[0]["location_type"], "city")

    def test_city_only_template_indices_empty_default(self) -> None:
        """When cityOnlySearchTemplateIndices is absent, all templates produce suburb tasks.

        Backward compatibility: 1 template × (1 city + 1 suburb) = 2 tasks.
        """
        self._write_categories({
            "RESTAURANT": {
                "displayName": "Restaurants",
                "searchTemplates": ["Filipino restaurant in {city}"],
            },
        })
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertEqual(len(tasks), 2)
        types = [t["location_type"] for t in tasks]
        self.assertIn("city", types)
        self.assertIn("suburb", types)

    def test_city_only_template_indices_combined_with_category_city_only(self) -> None:
        """When a category is cityOnly, cityOnlySearchTemplateIndices has no additional effect.

        Category-level cityOnly already skips all suburb tasks regardless of template indices.
        """
        self._write_categories({
            "GOVERNMENT": {
                "displayName": "Government",
                "cityOnly": True,
                "searchTemplates": [
                    "Philippine consulate in {city}",
                    "Filipino embassy in {city}",
                ],
                "cityOnlySearchTemplateIndices": [0],
            },
        })
        tasks = generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        # cityOnly means all templates are city-only: 2 templates × 1 city = 2
        self.assertEqual(len(tasks), 2)
        for task in tasks:
            self.assertEqual(task["location_type"], "city")

    def test_city_only_template_indices_out_of_bounds_raises(self) -> None:
        """Out-of-bounds indices in cityOnlySearchTemplateIndices raise ValueError."""
        self._write_categories({
            "RESTAURANT": {
                "displayName": "Restaurants",
                "searchTemplates": ["Filipino restaurant in {city}"],
                "cityOnlySearchTemplateIndices": [99],
            },
        })
        with self.assertRaises(ValueError) as ctx:
            generate_tasks("Sydney", self.categories_path, self.suburbs_path)
        self.assertIn("99", str(ctx.exception))
        self.assertIn("RESTAURANT", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
