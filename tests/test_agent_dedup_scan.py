"""Unit tests for the dedup scan CLI script.

Tests the scan, plan, verdict, execute, and summary actions with mocked
GraphQL operations.
"""

import asyncio
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch


# Add project root to path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
)


def _make_listing(**overrides):
    """Factory for test listing dicts."""
    base = {
        "id": "uuid-default",
        "name": "Default Business",
        "address": "123 Main St",
        "city": "SYDNEY",
        "categories": ["RESTAURANT"],
        "verificationStatus": "VERIFIED",
        "status": "OPERATIONAL",
        "sourceUrl": None,
        "createdAt": "2026-01-01T00:00:00Z",
        "lastEnrichedAt": None,
        "phone": None,
        "website": None,
        "email": None,
        "facebookUrl": None,
        "instagramUrl": None,
        "tiktokUrl": None,
        "description": None,
        "operatingHours": None,
        "imageUrl": None,
        "tags": None,
        "latitude": -33.8688,
        "longitude": 151.2093,
    }
    base.update(overrides)
    return base


# Duplicate pair for testing
LISTING_A = _make_listing(
    id="uuid-a",
    name="CJ Migration",
    address="123 Anzac Parade, Kensington NSW 2033",
    createdAt="2026-01-15T00:00:00Z",
    phone="0412345678",
    website="https://cjmigration.com.au",
)
LISTING_B = _make_listing(
    id="uuid-b",
    name="CJMigration",
    address="123 Anzac Pde, Kensington NSW 2033",
    createdAt="2026-03-20T00:00:00Z",
    email="info@cjmigration.com.au",
)
# Non-duplicate listing
LISTING_C = _make_listing(
    id="uuid-c",
    name="Manila Grill Restaurant",
    address="456 George St, Sydney NSW 2000",
    createdAt="2026-02-01T00:00:00Z",
)


class TestPlanAction(unittest.TestCase):
    """Tests for --action plan."""

    def test_plan_creates_file_with_correct_structure(self):
        from scripts.agent_dedup_scan import generate_plan

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            listings = [LISTING_A, LISTING_B, LISTING_C]

            generate_plan(
                city="SYDNEY",
                listings=listings,
                plan_path=plan_path,
                trace_id="test-trace",
            )

            self.assertTrue(os.path.exists(plan_path))
            with open(plan_path) as f:
                plan = json.load(f)

            self.assertEqual(plan["city"], "SYDNEY")
            self.assertIn("generatedAt", plan)
            self.assertIn("groups", plan)
            self.assertIn("stats", plan)
            self.assertIsInstance(plan["groups"], list)

    def test_plan_detects_fuzzy_duplicate(self):
        from scripts.agent_dedup_scan import generate_plan

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            listings = [LISTING_A, LISTING_B, LISTING_C]

            generate_plan(
                city="SYDNEY",
                listings=listings,
                plan_path=plan_path,
                trace_id="test-trace",
            )

            with open(plan_path) as f:
                plan = json.load(f)

            # Should find 1 duplicate group (CJ Migration / CJMigration)
            self.assertEqual(len(plan["groups"]), 1)
            group = plan["groups"][0]
            candidate_ids = {c["id"] for c in group["candidates"]}
            self.assertEqual(candidate_ids, {"uuid-a", "uuid-b"})

    def test_plan_idempotent_warns_existing_verdicts(self):
        from scripts.agent_dedup_scan import generate_plan

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")

            # First plan
            generate_plan("SYDNEY", [LISTING_A, LISTING_B], plan_path, "t1")
            # Simulate verdict
            with open(plan_path) as f:
                plan = json.load(f)
            plan["groups"][0]["verdict"] = "CONFIRMED_DUPLICATE"
            with open(plan_path, "w") as f:
                json.dump(plan, f)

            # Regenerate (should overwrite, losing verdicts)
            generate_plan("SYDNEY", [LISTING_A, LISTING_B], plan_path, "t2")
            with open(plan_path) as f:
                plan = json.load(f)
            self.assertIsNone(plan["groups"][0]["verdict"])


class TestVerdictAction(unittest.TestCase):
    """Tests for --action verdict."""

    def _create_plan(self, plan_path):
        from scripts.agent_dedup_scan import generate_plan
        generate_plan("SYDNEY", [LISTING_A, LISTING_B], plan_path, "t1")

    def test_verdict_records_confirmed_duplicate(self):
        from scripts.agent_dedup_scan import record_verdict

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            self._create_plan(plan_path)

            record_verdict(
                plan_path=plan_path,
                group_id=1,
                verdict="CONFIRMED_DUPLICATE",
                survivor_id="uuid-a",
                reasoning="Same business, name differs by spacing",
                trace_id="test-trace",
            )

            with open(plan_path) as f:
                plan = json.load(f)
            group = plan["groups"][0]
            self.assertEqual(group["verdict"], "CONFIRMED_DUPLICATE")
            self.assertEqual(group["survivorId"], "uuid-a")
            self.assertEqual(group["duplicateIds"], ["uuid-b"])
            self.assertEqual(group["reasoning"], "Same business, name differs by spacing")

    def test_verdict_records_false_positive(self):
        from scripts.agent_dedup_scan import record_verdict

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            self._create_plan(plan_path)

            record_verdict(
                plan_path=plan_path,
                group_id=1,
                verdict="FALSE_POSITIVE",
                survivor_id=None,
                reasoning="Different businesses despite similar names",
                trace_id="test-trace",
            )

            with open(plan_path) as f:
                plan = json.load(f)
            group = plan["groups"][0]
            self.assertEqual(group["verdict"], "FALSE_POSITIVE")
            self.assertIsNone(group["survivorId"])

    def test_verdict_invalid_group_id_raises(self):
        from scripts.agent_dedup_scan import record_verdict

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            self._create_plan(plan_path)

            with self.assertRaises(ValueError):
                record_verdict(
                    plan_path=plan_path,
                    group_id=999,
                    verdict="CONFIRMED_DUPLICATE",
                    survivor_id="uuid-a",
                    reasoning="test",
                    trace_id="test-trace",
                )


class TestExecuteAction(unittest.TestCase):
    """Tests for --action execute."""

    def _create_confirmed_plan(self, plan_path):
        from scripts.agent_dedup_scan import generate_plan, record_verdict
        generate_plan("SYDNEY", [LISTING_A, LISTING_B], plan_path, "t1")
        record_verdict(plan_path, 1, "CONFIRMED_DUPLICATE", "uuid-a",
                       "Same business", "t1")

    @patch("features.shared.graphql_client.execute_graphql_operation", new_callable=AsyncMock)
    def test_execute_merges_and_deletes(self, mock_gql):
        from scripts.agent_dedup_scan import execute_plan
        mock_gql.return_value = {"data": {"listing_delete": {"id": "uuid-b"}}}

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            self._create_confirmed_plan(plan_path)

            stats = asyncio.run(execute_plan(plan_path, "test-trace"))

            # Should have called UpdateListingData (merge) + DeleteListing (delete)
            call_ops = [call.kwargs.get("operation_name") or call.args[0]
                        for call in mock_gql.call_args_list]
            self.assertIn("UpdateListingData", call_ops)
            self.assertIn("DeleteListing", call_ops)
            self.assertEqual(stats["groups_executed"], 1)
            self.assertEqual(stats["listings_deleted"], 1)

    @patch("features.shared.graphql_client.execute_graphql_operation", new_callable=AsyncMock)
    def test_execute_skips_false_positives(self, mock_gql):
        from scripts.agent_dedup_scan import generate_plan, record_verdict, execute_plan

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            generate_plan("SYDNEY", [LISTING_A, LISTING_B], plan_path, "t1")
            record_verdict(plan_path, 1, "FALSE_POSITIVE", None,
                           "Different businesses", "t1")

            stats = asyncio.run(execute_plan(plan_path, "test-trace"))
            mock_gql.assert_not_called()
            self.assertEqual(stats["groups_executed"], 0)
            self.assertEqual(stats["listings_deleted"], 0)

    @patch("features.shared.graphql_client.execute_graphql_operation", new_callable=AsyncMock)
    def test_execute_skips_already_executed(self, mock_gql):
        from scripts.agent_dedup_scan import execute_plan

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            self._create_confirmed_plan(plan_path)

            # Mark as already executed
            with open(plan_path) as f:
                plan = json.load(f)
            plan["groups"][0]["executedAt"] = "2026-06-01T00:00:00Z"
            with open(plan_path, "w") as f:
                json.dump(plan, f)

            stats = asyncio.run(execute_plan(plan_path, "test-trace"))
            mock_gql.assert_not_called()
            self.assertEqual(stats["groups_executed"], 0)


class TestSummaryAction(unittest.TestCase):
    """Tests for --action summary."""

    def test_summary_counts(self):
        from scripts.agent_dedup_scan import generate_plan, record_verdict, get_summary

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            generate_plan("SYDNEY", [LISTING_A, LISTING_B], plan_path, "t1")

            summary = get_summary(plan_path)
            self.assertEqual(summary["total_groups"], 1)
            self.assertEqual(summary["pending_verdicts"], 1)
            self.assertEqual(summary["confirmed_duplicates"], 0)
            self.assertEqual(summary["false_positives"], 0)

    def test_summary_after_verdict(self):
        from scripts.agent_dedup_scan import generate_plan, record_verdict, get_summary

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = os.path.join(tmpdir, "dedup_plan_SYDNEY.json")
            generate_plan("SYDNEY", [LISTING_A, LISTING_B], plan_path, "t1")
            record_verdict(plan_path, 1, "CONFIRMED_DUPLICATE", "uuid-a",
                           "Same business", "t1")

            summary = get_summary(plan_path)
            self.assertEqual(summary["pending_verdicts"], 0)
            self.assertEqual(summary["confirmed_duplicates"], 1)
            self.assertEqual(summary["listings_to_delete"], 1)


if __name__ == "__main__":
    unittest.main()
