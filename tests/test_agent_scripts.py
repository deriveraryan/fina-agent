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


    @patch("agent_fetch_targets.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_fetch_targets_missing_social(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_fetch_targets.py --type missing-social invokes ListListingsMissingSocial."""
        import agent_fetch_targets

        sys.argv = ["agent_fetch_targets.py", "--type", "missing-social", "--city", "SYDNEY"]
        
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {"id": "123", "name": "Pinoy Cafe"}
                ]
            }
        }

        await agent_fetch_targets.main()

        mock_execute.assert_called_once_with(
            operation_name="ListListingsMissingSocial",
            variables={"city": "SYDNEY"}
        )
        mock_stdout.write.assert_any_call(
            json.dumps([{"id": "123", "name": "Pinoy Cafe"}])
        )

    @patch("agent_fetch_targets.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_fetch_targets_business_socials(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_fetch_targets.py --type business-socials invokes ListCityListings and extracts social URLs."""
        import agent_fetch_targets

        sys.argv = ["agent_fetch_targets.py", "--type", "business-socials", "--city", "SYDNEY"]
        
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

        await agent_fetch_targets.main()

        mock_execute.assert_called_once_with(
            operation_name="ListCityListings",
            variables={"city": "SYDNEY"}
        )
        # Should flatten and filter out None values, returning objects with id and url
        expected_targets = [
            {"id": "1", "url": "https://facebook.com/1"},
            {"id": "1", "url": "https://instagram.com/1"},
            {"id": "2", "url": "https://instagram.com/2"},
            {"id": "3", "url": "https://facebook.com/3"}
        ]
        mock_stdout.write.assert_any_call(
            json.dumps(expected_targets)
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
        )

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("builtins.open")
    async def test_graphql_push_executes_mutation_with_file_variable(self, mock_open: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_graphql_push.py resolves the file path when variables starts with @."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "UpdateListingSocialUrls",
            "--variables",
            "@tmp/my_variables.json"
        ]

        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = '{"id": "123", "facebookUrl": "https://facebook.com/resto"}'
        mock_open.return_value = mock_file

        mock_execute.return_value = {"data": {"updateListingSocialUrls": {"id": "123"}}}

        await agent_graphql_push.main()

        mock_open.assert_called_once_with("tmp/my_variables.json", "r")
        mock_execute.assert_called_once_with(
            operation_name="UpdateListingSocialUrls",
            variables={"id": "123", "facebookUrl": "https://facebook.com/resto"},
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
                "reviews": [
                    {
                        "externalSourceId": "places/place1/reviews/0",
                        "authorName": "John Doe",
                        "rating": 5.0,
                        "text": "Great food",
                        "publishedDate": "2026-06-06T00:00:00Z"
                    },
                    {
                        "externalSourceId": "places/place1/reviews/1",
                        "authorName": "Jane Smith",
                        "rating": 4.0,
                        "text": "Loved the adobo",
                        "publishedDate": "2026-06-06T00:00:00Z"
                    }
                ],
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
                "reviews": [
                    {
                        "externalSourceId": "places/place2/reviews/0",
                        "authorName": "Alice",
                        "rating": 5.0,
                        "text": "Best ube latte",
                        "publishedDate": "2026-06-06T00:00:00Z"
                    },
                    {
                        "externalSourceId": "places/place2/reviews/1",
                        "authorName": "Bob",
                        "rating": 4.5,
                        "text": "Pandesal was fresh",
                        "publishedDate": "2026-06-06T00:00:00Z"
                    }
                ],
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
                    "businessStatus": "CLOSED_TEMPORARILY",
                    "types": ["restaurant", "food"],
                    "formattedAddress": "123 Live St",
                    "location": {"latitude": -33.8, "longitude": 151.2},
                    "internationalPhoneNumber": "+61 2 8888 8888",
                    "websiteUri": "https://live.example.com",
                    "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9:00 AM – 5:00 PM"]},
                    "editorialSummary": {"text": "Live summary"},
                    "reviews": [
                        {
                            "name": "places/place_live_1/reviews/0",
                            "authorAttribution": {"displayName": "Juan Dela Cruz"},
                            "rating": 5.0,
                            "text": {"text": "Delicious adobo"},
                            "publishTime": "2026-06-06T00:00:00Z"
                        }
                    ]
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
        self.assertEqual(parsed_output["places"][0]["status"], "CLOSED_TEMPORARILY")
        self.assertEqual(parsed_output["total"], 1)
        self.assertFalse(parsed_output["has_more"])

    @patch("agent_fetch_targets.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_fetch_targets_city_listings(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_fetch_targets.py --type city-listings invokes ListCityListings and formats ID, name, fb/ig URLs."""
        import agent_fetch_targets

        sys.argv = ["agent_fetch_targets.py", "--type", "city-listings", "--city", "SYDNEY"]
        
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {
                        "id": "listing-1",
                        "name": "Manila Eats",
                        "facebookUrl": "https://facebook.com/manilaeats",
                        "instagramUrl": "https://instagram.com/manilaeats",
                        "otherField": "unused"
                    }
                ]
            }
        }

        await agent_fetch_targets.main()

        mock_execute.assert_called_once_with(
            operation_name="ListCityListings",
            variables={"city": "SYDNEY"}
        )
        mock_stdout.write.assert_any_call(
            json.dumps([
                {
                    "id": "listing-1",
                    "name": "Manila Eats",
                    "facebookUrl": "https://facebook.com/manilaeats",
                    "instagramUrl": "https://instagram.com/manilaeats"
                }
            ])
        )

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
            '{"name": "Duplicate Resto", "category": "RESTAURANT", "city": "SYDNEY", "description": "Filipino diner", "facebookUrl": "fb.com/new", "reviews": [{"text": "Good", "rating": 4.5, "externalSourceId": "rev1"}]}'
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
            "instagramUrl": "ig.com/new",
            "status": "CLOSED_TEMPORARILY"
        }
        mock_merge.return_value = merged_listing

        await agent_graphql_push.main()

        mock_check.assert_called_once_with(
            name="Duplicate Resto",
            city="SYDNEY",
            description="Filipino diner",
            source_url=None,
            categories=["RESTAURANT"],
            trace_id=None,
        )
        mock_merge.assert_called_once()
        
        # Verify it updates existing listing
        update_calls = [
            call.kwargs.get("operation_name") or call.args[0]
            for call in mock_execute.call_args_list
        ]
        self.assertIn("UpdateListingStatus", update_calls)
        self.assertIn("UpdateListingData", update_calls)
        self.assertIn("CreateReview", update_calls)
        
        mock_execute.assert_any_call("CreateReview", {"text": "Good", "rating": 4.5, "externalSourceId": "rev1", "listingId": "existing-123"})
        
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
                "sourceUrl": None,
                "status": "CLOSED_TEMPORARILY",
                "facebookFollowers": None,
                "instagramFollowers": None
            },
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
            '{"name": "New Resto", "category": "RESTAURANT", "city": "SYDNEY", "address": "123 St", "description": "Good food", "status": "OPERATIONAL", "reviews": [{"text": "Nice place!", "rating": 5.0, "externalSourceId": "review1"}]}'
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
            source_url=None,
            categories=["RESTAURANT"],
            trace_id=None,
        )
        mock_geocode.assert_called_once_with("123 St", "SYDNEY")
        mock_embedding.assert_called_once_with(
            "New Resto is a Filipino RESTAURANT located in SYDNEY. Good food",
            conversation_id=None
        )
        
        mock_execute.assert_any_call(
            operation_name="CreateListing",
            variables={
                "name": "New Resto",
                "categories": ["RESTAURANT"],
                "city": "SYDNEY",
                "address": "123 St",
                "description": "Good food",
                "latitude": -33.8688,
                "longitude": 151.2093,
                "descriptionEmbedding": [0.1, 0.2, 0.3],
                "verificationStatus": "UNVERIFIED",
                "status": "OPERATIONAL"
            },
        )
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        self.assertEqual(parsed_output["data"]["createListing"]["id"], "new-999")
        
        mock_execute.assert_any_call("CreateReview", {"text": "Nice place!", "rating": 5.0, "externalSourceId": "review1", "listingId": "new-999"})

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
    @patch("features.scanning.sources.geocoder.geocode_address", new_callable=AsyncMock)
    @patch("features.shared.embeddings.get_embedding")
    @patch("sys.stdout")
    async def test_graphql_push_category_validation_valid(
        self, mock_stdout: MagicMock, mock_embedding: MagicMock, mock_geocode: AsyncMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_graphql_push.py normalizes lowercase categories and pushes successfully."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "New Resto", "category": "restaurant", "city": "SYDNEY", "address": "123 St"}'
        ]

        mock_check.return_value = None
        mock_geocode.return_value = (-33.8688, 151.2093)
        mock_embedding.return_value = [0.1, 0.2, 0.3]
        mock_execute.return_value = {"data": {"createListing": {"id": "new-999"}}}

        await agent_graphql_push.main()

        # The category should be normalized to uppercase RESTAURANT in variables
        mock_execute.assert_any_call(
            operation_name="CreateListing",
            variables={
                "name": "New Resto",
                "categories": ["RESTAURANT"],
                "city": "SYDNEY",
                "address": "123 St",
                "latitude": -33.8688,
                "longitude": 151.2093,
                "descriptionEmbedding": [0.1, 0.2, 0.3],
                "verificationStatus": "UNVERIFIED"
            },
        )

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stderr")
    async def test_graphql_push_category_validation_invalid(self, mock_stderr: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests that agent_graphql_push.py exits with code 1 if category is invalid."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "New Resto", "category": "NOT_A_CATEGORY", "city": "SYDNEY"}'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: Category 'NOT_A_CATEGORY' is not a valid category in the database.", stderr_calls)


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
            '123'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: Variables must be a JSON object or a list of JSON objects.", stderr_calls)

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

    @patch("agent_fetch_targets.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout.write")
    @patch("sys.stderr.write")
    async def test_agent_fetch_targets_cli_logging_to_stderr(
        self, mock_stderr_write: MagicMock, mock_stdout_write: MagicMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_fetch_targets.py logs to stderr and outputs JSON to stdout."""
        import agent_fetch_targets

        sys.argv = ["agent_fetch_targets.py", "--type", "missing-social", "--city", "SYDNEY"]
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {"id": "123", "name": "Pinoy Cafe"}
                ]
            }
        }

        await agent_fetch_targets.main()

        # Check stdout has correct JSON
        mock_stdout_write.assert_called()
        stdout_calls = "".join(call.args[0] for call in mock_stdout_write.call_args_list)
        parsed = json.loads(stdout_calls)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["name"], "Pinoy Cafe")

        # Check stderr has logs
        mock_stderr_write.assert_called()
        stderr_calls = "".join(call.args[0] for call in mock_stderr_write.call_args_list)
        self.assertIn("[INFO] Starting agent_fetch_targets.py with type=missing-social, city=SYDNEY", stderr_calls)
        self.assertIn("[INFO] Retrieved 1 listings missing social media links.", stderr_calls)

    @patch("agent_fetch_targets.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout.write")
    @patch("sys.stderr.write")
    async def test_agent_fetch_targets_with_trace_id(
        self, mock_stderr_write: MagicMock, mock_stdout_write: MagicMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_fetch_targets.py parses and propagates --trace-id to logs."""
        import agent_fetch_targets

        sys.argv = ["agent_fetch_targets.py", "--type", "missing-social", "--city", "SYDNEY", "--trace-id", "test-trace-123"]
        mock_execute.return_value = {"data": {"listings": []}}

        await agent_fetch_targets.main()

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

    @patch("sys.stderr")
    async def test_graphql_push_validation_invalid_facebook_followers_type(self, mock_stderr: MagicMock) -> None:
        """Tests agent_graphql_push.py exits with code 1 if facebookFollowers is not an integer."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Some Resto", "city": "SYDNEY", "facebookFollowers": "not-an-int"}'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: 'facebookFollowers' must be an integer if provided.", stderr_calls)

    @patch("sys.stderr")
    async def test_graphql_push_validation_invalid_instagram_followers_type(self, mock_stderr: MagicMock) -> None:
        """Tests agent_graphql_push.py exits with code 1 if instagramFollowers is not an integer."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Some Resto", "city": "SYDNEY", "instagramFollowers": "not-an-int"}'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: 'instagramFollowers' must be an integer if provided.", stderr_calls)

    def test_merge_listing_data_overwrites_followers(self) -> None:
        """Tests that merge_listing_data overwrites existing follower counts with new ones."""
        from features.scanning.dedup import merge_listing_data

        existing = {
            "id": "123",
            "name": "Test Resto",
            "facebookFollowers": 100,
            "instagramFollowers": 200,
        }
        new_data = {
            "facebookFollowers": 150,
            "instagramFollowers": None,
        }

        merged = merge_listing_data(existing, new_data)
        self.assertEqual(merged["facebookFollowers"], 150)
        self.assertEqual(merged["instagramFollowers"], 200)

    @patch("agent_fetch_targets.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_fetch_targets_social_post_tracker_success(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_fetch_targets.py --type social-post-tracker invokes GetSocialPostTracker and formats output."""
        import agent_fetch_targets

        sys.argv = [
            "agent_fetch_targets.py",
            "--type",
            "social-post-tracker",
            "--listing-id",
            "listing-abc",
            "--platform",
            "facebook"
        ]

        mock_execute.return_value = {
            "data": {
                "socialPostTrackers": [
                    {
                        "id": "tracker-123",
                        "listingId": "listing-abc",
                        "platform": "FACEBOOK",
                        "lastPostDate": "2026-06-09T00:00:00Z"
                    }
                ]
            }
        }

        await agent_fetch_targets.main()

        mock_execute.assert_called_once_with(
            operation_name="GetSocialPostTracker",
            variables={"listingId": "listing-abc", "platform": "FACEBOOK"}
        )
        mock_stdout.write.assert_any_call(
            json.dumps({
                "id": "tracker-123",
                "listingId": "listing-abc",
                "platform": "FACEBOOK",
                "lastPostDate": "2026-06-09T00:00:00Z"
            })
        )

    @patch("sys.stderr")
    async def test_fetch_targets_social_post_tracker_missing_args(self, mock_stderr: MagicMock) -> None:
        """Tests agent_fetch_targets.py --type social-post-tracker validation fails when listing-id or platform is missing."""
        import agent_fetch_targets

        sys.argv = [
            "agent_fetch_targets.py",
            "--type",
            "social-post-tracker",
            "--listing-id",
            "listing-abc"
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_fetch_targets.main()
        self.assertEqual(cm.exception.code, 1)

        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: --listing-id and --platform are required for social-post-tracker", stderr_calls)

    @patch("sys.stdout")
    @patch("os.path.exists")
    async def test_maps_fetch_services_success(self, mock_exists: MagicMock, mock_stdout: MagicMock) -> None:
        """Tests that agent_maps_fetch.py supports SERVICES category and returns mock data offline."""
        import agent_maps_fetch

        mock_exists.return_value = False
        sys.argv = ["agent_maps_fetch.py", "--city", "SYDNEY", "--category", "SERVICES", "--limit", "10", "--offset", "0"]
        
        await agent_maps_fetch.main()

        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        
        self.assertEqual(parsed_output["total"], 1)
        self.assertEqual(parsed_output["places"][0]["name"], "Mock Services Business Sydney")
        self.assertEqual(parsed_output["places"][0]["description"], "A verified Filipino services in Sydney.")

    @patch("agent_audit_listings.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_audit_listings_success(
        self, mock_stdout: MagicMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_audit_listings.py queries listings and outputs paginated JSON to stdout."""
        import agent_audit_listings

        # Mock listing data from GraphQL query
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {
                        "id": "listing-abc",
                        "name": "Pinoy Freight Sydney",
                        "categories": ["COMMUNITY"],
                        "city": "SYDNEY",
                        "description": "Balikbayan box cargo forwarding services to the Philippines.",
                        "tags": "filipino,community,cargo"
                    }
                ]
            }
        }

        sys.argv = ["agent_audit_listings.py", "--city", "SYDNEY", "--limit", "10", "--offset", "0"]
        
        await agent_audit_listings.main()

        # Check GraphQL query
        mock_execute.assert_called_once_with(
            operation_name="ListCityListings",
            variables={"city": "SYDNEY"}
        )

        # Check output printed to stdout
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        
        self.assertEqual(parsed_output["total"], 1)
        self.assertFalse(parsed_output["has_more"])
        self.assertEqual(len(parsed_output["listings"]), 1)
        self.assertEqual(parsed_output["listings"][0]["id"], "listing-abc")
        self.assertEqual(parsed_output["listings"][0]["name"], "Pinoy Freight Sydney")
        self.assertEqual(parsed_output["listings"][0]["categories"], ["COMMUNITY"])
        self.assertEqual(parsed_output["listings"][0]["description"], "Balikbayan box cargo forwarding services to the Philippines.")
        self.assertEqual(parsed_output["listings"][0]["tags"], "filipino,community,cargo")

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("features.scanning.dedup.check_duplicate", new_callable=AsyncMock)
    @patch("features.scanning.dedup.merge_listing_data")
    @patch("sys.stdout")
    async def test_graphql_push_duplicate_review_ignored(
        self, mock_stdout: MagicMock, mock_merge: MagicMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_graphql_push.py handles review unique constraint violations gracefully."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Duplicate Resto", "category": "RESTAURANT", "city": "SYDNEY", "description": "Filipino diner", "facebookUrl": "fb.com/new", "reviews": [{"text": "Good", "rating": 4.5, "externalSourceId": "rev1"}]}'
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
        mock_merge.return_value = existing_listing

        # Mock execute_graphql_operation to raise unique constraint error when calling CreateReview
        def side_effect(operation_name, variables=None):
            if operation_name == "CreateReview":
                raise RuntimeError("GraphQL Execution Error: unique constraint review_externalSourceId_uidx violation")
            return {"data": {}}

        mock_execute.side_effect = side_effect

        await agent_graphql_push.main()

        # The script should not raise an exception and should output status MERGED
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        self.assertEqual(parsed_output["status"], "MERGED")
        self.assertEqual(parsed_output["existingId"], "existing-123")

