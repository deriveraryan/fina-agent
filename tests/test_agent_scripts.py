"""Offline unit tests for the agent helper scripts in scripts/.

Part of the TDD cycle.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

# Add scripts directory to path to allow importing agent scripts
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

class TestAgentScripts(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for agent helper CLI scripts."""

    def setUp(self) -> None:
        self._orig_argv = list(sys.argv)

    def tearDown(self) -> None:
        sys.argv = self._orig_argv


    @patch("agent_get_seeds.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_get_seeds_missing_social(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_get_seeds.py --type missing-social invokes ListListingsMissingSocial."""
        import agent_get_seeds

        sys.argv = ["agent_get_seeds.py", "--type", "missing-social", "--city", "SYDNEY"]
        
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {"id": "123", "name": "Pinoy Cafe"}
                ]
            }
        }

        await agent_get_seeds.main()

        mock_execute.assert_called_once_with(
            operation_name="ListListingsMissingSocial",
            variables={"city": "SYDNEY"}
        )
        mock_stdout.write.assert_any_call(
            json.dumps([{"id": "123", "name": "Pinoy Cafe"}])
        )

    @patch("agent_get_seeds.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_get_seeds_business_socials(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_get_seeds.py --type business-socials invokes ListCityListings and extracts social URLs."""
        import agent_get_seeds

        sys.argv = ["agent_get_seeds.py", "--type", "business-socials", "--city", "SYDNEY"]
        
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {"id": "1", "facebookUrl": "https://facebook.com/1", "instagramUrl": "https://instagram.com/1"},
                    {"id": "2", "facebookUrl": None, "instagramUrl": "https://instagram.com/2"},
                    {"id": "3", "facebookUrl": "https://facebook.com/3", "instagramUrl": None},
                    {"id": "4", "facebookUrl": None, "instagramUrl": None}
                ]
            }
        }

        await agent_get_seeds.main()

        mock_execute.assert_called_once_with(
            operation_name="ListCityListings",
            variables={"city": "SYDNEY"}
        )
        # Should flatten and filter out None values
        expected_urls = [
            "https://facebook.com/1",
            "https://instagram.com/1",
            "https://instagram.com/2",
            "https://facebook.com/3"
        ]
        mock_stdout.write.assert_any_call(
            json.dumps(expected_urls)
        )

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    async def test_graphql_push_executes_mutation(self, mock_execute: AsyncMock) -> None:
        """Tests agent_graphql_push.py takes operation name and variables and executes them generically."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "UpdateListingSocialUrls",
            "--variables",
            '{"id": "123", "facebookUrl": "https://facebook.com/resto"}'
        ]

        mock_execute.return_value = {"data": {"updateListingSocialUrls": {"id": "123"}}}

        await agent_graphql_push.main()

        mock_execute.assert_called_once_with(
            operation_name="UpdateListingSocialUrls",
            variables={"id": "123", "facebookUrl": "https://facebook.com/resto"},
            force_production=False
        )

    @patch("sys.stdout")
    @patch("os.path.exists")
    @patch("builtins.open")
    async def test_maps_fetch_cache_hit(self, mock_open: MagicMock, mock_exists: MagicMock, mock_stdout: MagicMock) -> None:
        """Tests that agent_maps_fetch.py reads from cache on cache hit."""
        import agent_maps_fetch

        mock_exists.return_value = True
        
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps([
            {
                "id": "place1",
                "name": "Manila Eats",
                "types": ["restaurant"],
                "address": "123 Pitt St",
                "latitude": -33.8688,
                "longitude": 151.2093,
                "phone": "+61 2 9999 1111",
                "website": "https://manilaeats.example.com",
                "hours": '{"mon": "11:00 AM – 9:00 PM"}',
                "description": "Filipino diner",
                "reviews": ["Great food", "Loved the adobo"],
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:place1"
            },
            {
                "id": "place2",
                "name": "Pinoy Brew",
                "types": ["cafe"],
                "address": "45 Pitt St",
                "latitude": -33.8695,
                "longitude": 151.2085,
                "phone": "+61 2 9999 2222",
                "website": "https://pinoybrew.example.com",
                "hours": '{"mon": "7:00 AM – 4:00 PM"}',
                "description": "Specialty ube lattes",
                "reviews": ["Best ube latte", "Pandesal was fresh"],
                "sourceUrl": "https://www.google.com/maps/place/?q=place_id:place2"
            }
        ])
        mock_open.return_value = mock_file

        sys.argv = ["agent_maps_fetch.py", "--city", "SYDNEY", "--category", "RESTAURANT", "--limit", "1", "--offset", "0"]
        
        await agent_maps_fetch.main()

        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        
        self.assertEqual(len(parsed_output["places"]), 1)
        self.assertEqual(parsed_output["places"][0]["name"], "Manila Eats")
        self.assertEqual(parsed_output["total"], 2)
        self.assertTrue(parsed_output["has_more"])

    @patch("sys.stdout")
    @patch("os.path.exists")
    @patch("builtins.open")
    @patch("httpx.AsyncClient.post")
    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "fake-key"})
    async def test_maps_fetch_cache_miss_live(self, mock_post: AsyncMock, mock_open: MagicMock, mock_exists: MagicMock, mock_stdout: MagicMock) -> None:
        """Tests that agent_maps_fetch.py fetches live on cache miss and writes cache."""
        import agent_maps_fetch

        mock_exists.return_value = False
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "places": [
                {
                    "id": "place_live_1",
                    "displayName": {"text": "Live Manila Eats"},
                    "types": ["restaurant", "food"],
                    "formattedAddress": "123 Live St",
                    "location": {"latitude": -33.8, "longitude": 151.2},
                    "internationalPhoneNumber": "+61 2 8888 8888",
                    "websiteUri": "https://live.example.com",
                    "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9:00 AM – 5:00 PM"]},
                    "editorialSummary": {"text": "Live summary"},
                    "reviews": [{"text": {"text": "Delicious adobo"}}]
                }
            ]
        }
        mock_post.return_value = mock_response

        mock_file = MagicMock()
        mock_open.return_value = mock_file

        sys.argv = ["agent_maps_fetch.py", "--city", "SYDNEY", "--category", "RESTAURANT", "--limit", "10", "--offset", "0"]
        
        await agent_maps_fetch.main()

        self.assertTrue(mock_post.called)
        mock_open.assert_called_with(unittest.mock.ANY, "w")
        
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        
        self.assertEqual(len(parsed_output["places"]), 1)
        self.assertEqual(parsed_output["places"][0]["name"], "Live Manila Eats")
        self.assertEqual(parsed_output["total"], 1)
        self.assertFalse(parsed_output["has_more"])

    @patch("agent_social_search.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    @patch("os.path.exists")
    @patch("builtins.open")
    async def test_social_search_cache_hit(self, mock_open: MagicMock, mock_exists: MagicMock, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests that agent_social_search.py reads from cache on cache hit and paginates."""
        import agent_social_search

        mock_exists.return_value = True
        mock_execute.return_value = {"data": {"listings": []}}

        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = json.dumps([
            {
                "url": "https://facebook.com/filipinoclub1",
                "name": "Filipino Basketball League Sydney",
                "description": "Community basketball league for Filipinos in Sydney",
                "platform": "facebook"
            },
            {
                "url": "https://facebook.com/filipinoclub2",
                "name": "Pinoy Runners Sydney",
                "description": "Running club for Filipino community",
                "platform": "facebook"
            },
            {
                "url": "https://facebook.com/filipinoclub3",
                "name": "Filipino Nurses Association",
                "description": "Professional network for Filipino nurses in Australia",
                "platform": "facebook"
            }
        ])
        mock_open.return_value = mock_file

        sys.argv = ["agent_social_search.py", "--city", "SYDNEY", "--category", "COMMUNITY", "--platform", "facebook", "--limit", "2", "--offset", "0"]

        await agent_social_search.main()

        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)

        self.assertEqual(len(parsed_output["candidates"]), 2)
        self.assertEqual(parsed_output["candidates"][0]["name"], "Filipino Basketball League Sydney")
        self.assertEqual(parsed_output["total"], 3)
        self.assertTrue(parsed_output["has_more"])

    @patch("agent_social_search.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    @patch("os.path.exists")
    @patch("builtins.open")
    async def test_social_search_cache_miss_mock(self, mock_open: MagicMock, mock_exists: MagicMock, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests that agent_social_search.py returns mock candidates on cache miss."""
        import agent_social_search

        mock_exists.return_value = False
        mock_execute.return_value = {"data": {"listings": []}}

        mock_file = MagicMock()
        mock_open.return_value = mock_file

        sys.argv = ["agent_social_search.py", "--city", "SYDNEY", "--category", "COMMUNITY", "--platform", "facebook", "--limit", "10", "--offset", "0"]

        await agent_social_search.main()

        # Verify cache was written
        mock_open.assert_called_with(unittest.mock.ANY, "w")

        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)

        # Mock mode should return at least 1 candidate
        self.assertGreaterEqual(len(parsed_output["candidates"]), 1)
        self.assertIn("url", parsed_output["candidates"][0])
        self.assertIn("name", parsed_output["candidates"][0])
        self.assertIn("platform", parsed_output["candidates"][0])
        self.assertIn("total", parsed_output)
        self.assertIn("has_more", parsed_output)

    @patch("agent_social_search.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    @patch("os.path.exists")
    @patch("builtins.open")
    async def test_social_search_deduplication(self, mock_open: MagicMock, mock_exists: MagicMock, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests that agent_social_search.py discards candidates already existing in Listing table."""
        import agent_social_search

        mock_exists.return_value = False
        mock_file = MagicMock()
        mock_open.return_value = mock_file

        # Mock Listing table already having candidate 1
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {
                        "facebookUrl": "https://facebook.com/mock-filipino-community-sydney-1",
                        "instagramUrl": None
                    }
                ]
            }
        }

        sys.argv = ["agent_social_search.py", "--city", "SYDNEY", "--category", "COMMUNITY", "--platform", "facebook", "--limit", "10", "--offset", "0"]

        await agent_social_search.main()

        # Check that ListCitySocialUrls was called
        mock_execute.assert_called_once_with(
            operation_name="ListCitySocialUrls",
            variables={"city": "SYDNEY"}
        )

        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)

        # Candidates should only have candidate 2 (candidate 1 is filtered out)
        self.assertEqual(len(parsed_output["candidates"]), 1)
        self.assertEqual(parsed_output["candidates"][0]["url"], "https://facebook.com/mock-filipino-community-sydney-2")
        self.assertEqual(parsed_output["total"], 1)
        self.assertFalse(parsed_output["has_more"])

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("features.scanning.dedup.check_duplicate", new_callable=AsyncMock)
    @patch("features.scanning.dedup.merge_listing_data")
    @patch("sys.stdout")
    async def test_graphql_push_duplicate_merged(
        self, mock_stdout: MagicMock, mock_merge: MagicMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests agent_graphql_push.py intercepts CreateListing, finds duplicate, merges, and updates it."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Duplicate Resto", "category": "RESTAURANT", "city": "SYDNEY", "description": "Filipino diner", "facebookUrl": "fb.com/new"}'
        ]

        existing_listing = {
            "id": "existing-123",
            "name": "Duplicate Resto",
            "categories": ["RESTAURANT"],
            "city": "SYDNEY",
            "description": "Filipino diner",
            "facebookUrl": "fb.com/old"
        }
        mock_check.return_value = existing_listing
        
        merged_listing = {
            "id": "existing-123",
            "name": "Duplicate Resto",
            "categories": ["RESTAURANT", "CAFE"],
            "city": "SYDNEY",
            "description": "Filipino diner",
            "facebookUrl": "fb.com/old",
            "instagramUrl": "ig.com/new"
        }
        mock_merge.return_value = merged_listing

        await agent_graphql_push.main()

        mock_check.assert_called_once_with(
            name="Duplicate Resto",
            city="SYDNEY",
            description="Filipino diner",
            force_production=False,
        )
        mock_merge.assert_called_once()
        
        # Verify it updates existing listing
        update_calls = [
            call.kwargs.get("operation_name") or call.args[0]
            for call in mock_execute.call_args_list
        ]
        self.assertIn("UpdateListingStatus", update_calls)
        self.assertIn("UpdateListingData", update_calls)
        
        # Verify specific update variables include categories list
        mock_execute.assert_any_call(
            operation_name="UpdateListingData",
            variables={
                "id": "existing-123",
                "categories": ["RESTAURANT", "CAFE"],
                "phone": None,
                "website": None,
                "facebookUrl": "fb.com/old",
                "instagramUrl": "ig.com/new",
                "tiktokUrl": None,
                "operatingHours": None,
                "imageUrl": None,
                "tags": None,
                "sourceUrl": None
            },
            force_production=False
        )
        
        # Verify output matches status MERGED
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        self.assertEqual(parsed_output["status"], "MERGED")
        self.assertEqual(parsed_output["existingId"], "existing-123")

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("features.scanning.dedup.check_duplicate", new_callable=AsyncMock)
    @patch("features.scanning.sources.geocoder.geocode_address", new_callable=AsyncMock)
    @patch("features.shared.embeddings.get_embedding")
    @patch("sys.stdout")
    async def test_graphql_push_no_duplicate_created(
        self, mock_stdout: MagicMock, mock_embedding: MagicMock, mock_geocode: AsyncMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests agent_graphql_push.py intercepts CreateListing, finds no duplicate, geocodes, gets embedding, and inserts."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "New Resto", "category": "RESTAURANT", "city": "SYDNEY", "address": "123 St", "description": "Good food"}'
        ]

        mock_check.return_value = None
        mock_geocode.return_value = (-33.8688, 151.2093)
        mock_embedding.return_value = [0.1, 0.2, 0.3]
        mock_execute.return_value = {"data": {"createListing": {"id": "new-999"}}}

        await agent_graphql_push.main()

        mock_check.assert_called_once_with(
            name="New Resto",
            city="SYDNEY",
            description="Good food",
            force_production=False,
        )
        mock_geocode.assert_called_once_with("123 St", "SYDNEY")
        mock_embedding.assert_called_once_with("Good food")
        
        mock_execute.assert_called_once_with(
            operation_name="CreateListing",
            variables={
                "name": "New Resto",
                "categories": ["RESTAURANT"],
                "city": "SYDNEY",
                "address": "123 St",
                "description": "Good food",
                "latitude": -33.8688,
                "longitude": 151.2093,
                "verificationStatus": "UNVERIFIED"
            },
            force_production=False
        )
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        self.assertEqual(parsed_output["data"]["createListing"]["id"], "new-999")

    @patch("sys.stderr")
    async def test_graphql_push_validation_missing_name(self, mock_stderr: MagicMock) -> None:
        """Tests agent_graphql_push.py exits with code 1 if name is missing."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"city": "SYDNEY"}'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: 'name' is required and must be a non-empty string.", stderr_calls)

    @patch("sys.stderr")
    async def test_graphql_push_validation_missing_city(self, mock_stderr: MagicMock) -> None:
        """Tests agent_graphql_push.py exits with code 1 if city is missing."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Some Resto"}'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: 'city' is required and must be a non-empty string.", stderr_calls)

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("features.scanning.dedup.check_duplicate", new_callable=AsyncMock)
    @patch("features.scanning.dedup.merge_listing_data")
    @patch("sys.stdout")
    @patch("sys.stderr")
    async def test_graphql_push_duplicate_merge_error_handled(
        self, mock_stderr: MagicMock, mock_stdout: MagicMock, mock_merge: MagicMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests agent_graphql_push.py handles exceptions during merge mutations gracefully."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Duplicate Resto", "city": "SYDNEY", "description": "Filipino diner", "facebookUrl": "fb.com/new"}'
        ]

        existing_listing = {
            "id": "existing-123",
            "name": "Duplicate Resto",
            "city": "SYDNEY",
            "description": "Filipino diner",
            "facebookUrl": "fb.com/old"
        }
        mock_check.return_value = existing_listing
        
        merged_listing = {
            "id": "existing-123",
            "name": "Duplicate Resto",
            "city": "SYDNEY",
            "description": "Filipino diner",
            "facebookUrl": "fb.com/old",
            "instagramUrl": "ig.com/new"
        }
        mock_merge.return_value = merged_listing
        
        mock_execute.side_effect = Exception("GraphQL connection timeout")

        await agent_graphql_push.main()

        # Verify output still matches status MERGED
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        self.assertEqual(parsed_output["status"], "MERGED")
        self.assertEqual(parsed_output["existingId"], "existing-123")
        
        # Verify stderr was written to
        mock_stderr.write.assert_called()

    @patch("sys.stderr")
    async def test_graphql_push_validation_invalid_variables_type(self, mock_stderr: MagicMock) -> None:
        """Tests agent_graphql_push.py exits with code 1 if variables is not a JSON object."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '[{"name": "Some Resto", "city": "SYDNEY"}]'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: Variables must be a JSON object/dictionary.", stderr_calls)

    @patch("sys.stderr")
    async def test_graphql_push_validation_invalid_description_type(self, mock_stderr: MagicMock) -> None:
        """Tests agent_graphql_push.py exits with code 1 if description is not a string."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Some Resto", "city": "SYDNEY", "description": 123}'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: 'description' must be a string if provided.", stderr_calls)

    @patch("agent_get_seeds.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout.write")
    @patch("sys.stderr.write")
    async def test_agent_get_seeds_cli_logging_to_stderr(
        self, mock_stderr_write: MagicMock, mock_stdout_write: MagicMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_get_seeds.py logs to stderr and outputs JSON to stdout."""
        import agent_get_seeds

        sys.argv = ["agent_get_seeds.py", "--type", "missing-social", "--city", "SYDNEY"]
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {"id": "123", "name": "Pinoy Cafe"}
                ]
            }
        }

        await agent_get_seeds.main()

        # Check stdout has correct JSON
        mock_stdout_write.assert_called()
        stdout_calls = "".join(call.args[0] for call in mock_stdout_write.call_args_list)
        parsed = json.loads(stdout_calls)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["name"], "Pinoy Cafe")

        # Check stderr has logs
        mock_stderr_write.assert_called()
        stderr_calls = "".join(call.args[0] for call in mock_stderr_write.call_args_list)
        self.assertIn("[INFO] Starting agent_get_seeds.py with type=missing-social, city=SYDNEY", stderr_calls)
        self.assertIn("[INFO] Retrieved 1 listings missing social media links.", stderr_calls)

    @patch("agent_get_seeds.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout.write")
    @patch("sys.stderr.write")
    async def test_agent_get_seeds_with_trace_id(
        self, mock_stderr_write: MagicMock, mock_stdout_write: MagicMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_get_seeds.py parses and propagates --trace-id to logs."""
        import agent_get_seeds

        sys.argv = ["agent_get_seeds.py", "--type", "missing-social", "--city", "SYDNEY", "--trace-id", "test-trace-123"]
        mock_execute.return_value = {"data": {"listings": []}}

        await agent_get_seeds.main()

        # Check stderr logs contain the trace/conversation ID context
        stderr_calls = "".join(call.args[0] for call in mock_stderr_write.call_args_list)
        self.assertIn("[Conv: test-trace-123]", stderr_calls)

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout.write")
    @patch("sys.stderr.write")
    async def test_graphql_push_with_trace_id(
        self, mock_stderr_write: MagicMock, mock_stdout_write: MagicMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_graphql_push.py parses and propagates --trace-id to logs."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "UpdateListingSocialUrls",
            "--variables",
            '{"id": "123"}',
            "--trace-id",
            "trace-456"
        ]
        mock_execute.return_value = {"data": {}}

        await agent_graphql_push.main()

        stderr_calls = "".join(call.args[0] for call in mock_stderr_write.call_args_list)
        self.assertIn("[Conv: trace-456]", stderr_calls)
