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

import features.shared.embeddings

class TestAgentScripts(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for agent helper CLI scripts."""

    def setUp(self) -> None:
        self._orig_argv = list(sys.argv)
        self._get_embedding_patcher = patch("features.shared.embeddings.get_embedding")
        self.mock_get_embedding = self._get_embedding_patcher.start()
        self.mock_get_embedding.return_value = [0.1] * 768

    def tearDown(self) -> None:
        sys.argv = self._orig_argv
        self._get_embedding_patcher.stop()


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
                    {"id": "1", "facebookUrl": "https://facebook.com/1", "instagramUrl": "https://instagram.com/1", "tiktokUrl": "https://tiktok.com/@1"},
                    {"id": "2", "facebookUrl": None, "instagramUrl": "https://instagram.com/2", "tiktokUrl": None},
                    {"id": "3", "facebookUrl": "https://facebook.com/3", "instagramUrl": None, "tiktokUrl": "https://tiktok.com/@3"},
                    {"id": "4", "facebookUrl": None, "instagramUrl": None, "tiktokUrl": None}
                ]
            }
        }

        await agent_fetch_targets.main()

        mock_execute.assert_called_once_with(
            operation_name="ListAdminListings",
            variables={
                "city": "SYDNEY",
                "limit": 1000,
                "verificationStatuses": ["VERIFIED", "UNVERIFIED"]
            }
        )
        # Should flatten and filter out None values, returning objects with id and url
        expected_targets = [
            {"id": "1", "url": "https://facebook.com/1"},
            {"id": "1", "url": "https://instagram.com/1"},
            {"id": "1", "url": "https://tiktok.com/@1"},
            {"id": "2", "url": "https://instagram.com/2"},
            {"id": "3", "url": "https://facebook.com/3"},
            {"id": "3", "url": "https://tiktok.com/@3"}
        ]
        mock_stdout.write.assert_any_call(
            json.dumps(expected_targets)
        )

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    async def test_graphql_push_executes_mutation(self, mock_execute: AsyncMock) -> None:
        """Tests agent_graphql_push.py executes the mutation with variables."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "UpdateListingSocialUrls",
            "--variables",
            '{"id": "123", "facebookUrl": "https://facebook.com/resto"}'
        ]

        def side_effect_fn(operation_name, variables):
            if operation_name == "GetListing":
                return {"data": {"listing": {"id": variables["id"], "facebookUrl": "https://facebook.com/resto"}}}
            return {"data": {"updateListingSocialUrls": {"id": variables["id"]}}}
        mock_execute.side_effect = side_effect_fn

        await agent_graphql_push.main()

        mock_execute.assert_any_call(
            operation_name="UpdateListingSocialUrls",
            variables={"id": "123", "facebookUrl": "https://www.facebook.com/resto", "instagramUrl": None, "tiktokUrl": None, "facebookFollowers": None, "instagramFollowers": None, "tiktokFollowers": None},
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

        def side_effect_fn(operation_name, variables):
            if operation_name == "GetListing":
                return {"data": {"listing": {"id": variables["id"], "facebookUrl": "https://facebook.com/resto"}}}
            return {"data": {"updateListingSocialUrls": {"id": variables["id"]}}}
        mock_execute.side_effect = side_effect_fn

        await agent_graphql_push.main()

        mock_open.assert_called_once_with("tmp/my_variables.json", "r")
        mock_execute.assert_any_call(
            operation_name="UpdateListingSocialUrls",
            variables={"id": "123", "facebookUrl": "https://www.facebook.com/resto", "instagramUrl": None, "tiktokUrl": None, "facebookFollowers": None, "instagramFollowers": None, "tiktokFollowers": None},
        )

    @patch("sys.stdout")
    @patch("httpx.AsyncClient.post")
    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "fake-key"})
    async def test_maps_fetch_single_query(self, mock_post: AsyncMock, mock_stdout: MagicMock) -> None:
        """Tests that agent_maps_fetch.py executes a single Places API query and returns formatted results."""
        import agent_maps_fetch

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "places": [
                {
                    "id": "place1",
                    "displayName": {"text": "Manila Eats"},
                    "types": ["restaurant", "food"],
                    "formattedAddress": "123 Pitt St",
                    "location": {"latitude": -33.8688, "longitude": 151.2093},
                    "internationalPhoneNumber": "+61 2 9999 1111",
                    "websiteUri": "https://manilaeats.example.com",
                    "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9:00 AM \u2013 5:00 PM"]},
                    "editorialSummary": {"text": "Filipino diner"},
                    "reviews": [],
                },
                {
                    "id": "place2",
                    "displayName": {"text": "Pinoy Brew"},
                    "types": ["cafe"],
                    "formattedAddress": "45 Pitt St",
                    "location": {"latitude": -33.8695, "longitude": 151.2085},
                    "internationalPhoneNumber": "+61 2 9999 2222",
                    "websiteUri": "https://pinoybrew.example.com",
                    "regularOpeningHours": {"weekdayDescriptions": ["Monday: 7:00 AM \u2013 4:00 PM"]},
                    "editorialSummary": {"text": "Specialty ube lattes"},
                    "reviews": [],
                },
            ]
        }
        mock_post.return_value = mock_response

        sys.argv = ["agent_maps_fetch.py", "--query", "Filipino restaurant in Sydney", "--city", "SYDNEY", "--category", "RESTAURANT"]

        await agent_maps_fetch.main()

        self.assertTrue(mock_post.called)
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)

        self.assertEqual(len(parsed_output["places"]), 2)
        self.assertEqual(parsed_output["total"], 2)
        self.assertEqual(parsed_output["places"][0]["name"], "Manila Eats")
        self.assertEqual(parsed_output["places"][1]["name"], "Pinoy Brew")

    @patch("sys.stdout")
    @patch("httpx.AsyncClient.post")
    @patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "fake-key"})
    async def test_maps_fetch_with_business_status(self, mock_post: AsyncMock, mock_stdout: MagicMock) -> None:
        """Tests that agent_maps_fetch.py correctly parses businessStatus and review fields."""
        import importlib
        import agent_maps_fetch
        importlib.reload(agent_maps_fetch)

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
                    "regularOpeningHours": {"weekdayDescriptions": ["Monday: 9:00 AM \u2013 5:00 PM"]},
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

        sys.argv = ["agent_maps_fetch.py", "--query", "Filipino restaurant in Sydney", "--city", "SYDNEY", "--category", "RESTAURANT"]

        await agent_maps_fetch.main()

        self.assertTrue(mock_post.called)
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)

        self.assertEqual(len(parsed_output["places"]), 1)
        self.assertEqual(parsed_output["places"][0]["name"], "Live Manila Eats")
        self.assertEqual(parsed_output["places"][0]["status"], "CLOSED_TEMPORARILY")
        self.assertEqual(parsed_output["total"], 1)

    @patch("agent_fetch_targets.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_fetch_targets_city_listings(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests agent_fetch_targets.py --type city-listings invokes ListCityListings and formats ID, name, fb/ig/tt URLs."""
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
                        "tiktokUrl": "https://tiktok.com/@manilaeats",
                        "otherField": "unused"
                    }
                ]
            }
        }

        await agent_fetch_targets.main()

        mock_execute.assert_called_once_with(
            operation_name="ListAdminListings",
            variables={
                "city": "SYDNEY",
                "limit": 1000,
                "verificationStatuses": ["VERIFIED", "UNVERIFIED"]
            }
        )
        mock_stdout.write.assert_any_call(
            json.dumps([
                {
                    "id": "listing-1",
                    "name": "Manila Eats",
                    "facebookUrl": "https://facebook.com/manilaeats",
                    "instagramUrl": "https://instagram.com/manilaeats",
                    "tiktokUrl": "https://tiktok.com/@manilaeats"
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
            generate_embeddings=False,
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
                "instagramFollowers": None,
                "tiktokFollowers": None
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
    @patch("sys.stdout")
    async def test_graphql_push_no_duplicate_created(
        self, mock_stdout: MagicMock, mock_geocode: AsyncMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests agent_graphql_push.py intercepts CreateListing, finds no duplicate, geocodes, and inserts with embeddingText."""
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
        mock_execute.return_value = {"data": {"createListing": {"id": "new-999"}}}

        await agent_graphql_push.main()

        mock_check.assert_called_once_with(
            name="New Resto",
            city="SYDNEY",
            description="Good food",
            source_url=None,
            categories=["RESTAURANT"],
            trace_id=None,
            generate_embeddings=False,
        )
        mock_geocode.assert_called_once_with("123 St", "SYDNEY")
        
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
                "verificationStatus": "UNVERIFIED",
                "descriptionEmbedding": None,
                "status": "OPERATIONAL"
            },
        )
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed_output = json.loads(combined_output)
        self.assertEqual(parsed_output["data"]["createListing"]["id"], "new-999")
        
        mock_execute.assert_any_call("CreateReview", {"text": "Nice place!", "rating": 5.0, "externalSourceId": "review1", "listingId": "new-999"})

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("features.scanning.dedup.check_duplicate", new_callable=AsyncMock)
    @patch("features.scanning.sources.geocoder.geocode_address", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_graphql_push_with_generate_embeddings(
        self, mock_stdout: MagicMock, mock_geocode: AsyncMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_graphql_push.py generates embeddings when --generate-embeddings is passed."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "New Resto", "category": "RESTAURANT", "city": "SYDNEY", "address": "123 St", "description": "Good food"}',
            "--generate-embeddings"
        ]

        mock_check.return_value = None
        mock_geocode.return_value = (-33.8688, 151.2093)
        mock_execute.return_value = {"data": {"createListing": {"id": "new-999"}}}

        await agent_graphql_push.main()

        mock_check.assert_called_once_with(
            name="New Resto",
            city="SYDNEY",
            description="Good food",
            source_url=None,
            categories=["RESTAURANT"],
            trace_id=None,
            generate_embeddings=True,
        )
        mock_geocode.assert_called_once_with("123 St", "SYDNEY")
        
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
                "verificationStatus": "UNVERIFIED",
                "descriptionEmbedding": [0.1] * 768
            },
        )

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
    @patch("sys.stdout")
    async def test_graphql_push_category_validation_valid(
        self, mock_stdout: MagicMock, mock_geocode: AsyncMock, mock_check: AsyncMock, mock_execute: AsyncMock
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
                "verificationStatus": "UNVERIFIED",
                "descriptionEmbedding": None
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
        def side_effect_fn(operation_name, variables):
            if operation_name == "GetListing":
                return {"data": {"listing": {"id": variables["id"]}}}
            return {"data": {}}
        mock_execute.side_effect = side_effect_fn

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

    @patch("sys.stderr")
    async def test_graphql_push_validation_invalid_tiktok_followers_type(self, mock_stderr: MagicMock) -> None:
        """Tests agent_graphql_push.py exits with code 1 if tiktokFollowers is not an integer."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Some Resto", "city": "SYDNEY", "tiktokFollowers": "not-an-int"}'
        ]

        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)
        stderr_calls = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("Validation Error: 'tiktokFollowers' must be an integer if provided.", stderr_calls)

    def test_merge_listing_data_overwrites_followers(self) -> None:
        """Tests that merge_listing_data overwrites existing follower counts with new ones."""
        from features.scanning.dedup import merge_listing_data

        existing = {
            "id": "123",
            "name": "Test Resto",
            "facebookFollowers": 100,
            "instagramFollowers": 200,
            "tiktokFollowers": 300,
        }
        new_data = {
            "facebookFollowers": 150,
            "instagramFollowers": None,
            "tiktokFollowers": 350,
        }

        merged = merge_listing_data(existing, new_data)
        self.assertEqual(merged["facebookFollowers"], 150)
        self.assertEqual(merged["instagramFollowers"], 200)
        self.assertEqual(merged["tiktokFollowers"], 350)

    def test_merge_listing_data_unions_categories(self) -> None:
        """Tests that merge_listing_data unions existing categories with incoming categories."""
        from features.scanning.dedup import merge_listing_data

        existing = {
            "id": "123",
            "name": "Test Cafe",
            "categories": ["RESTAURANT"],
        }
        new_data = {
            "categories": ["CAFE"],
        }

        merged = merge_listing_data(existing, new_data)
        self.assertEqual(sorted(merged["categories"]), sorted(["RESTAURANT", "CAFE"]))


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

    @patch("sys.stderr")
    async def test_maps_fetch_requires_api_key(self, mock_stderr: MagicMock) -> None:
        """Tests that agent_maps_fetch.py exits with code 1 when GOOGLE_MAPS_API_KEY is not set."""
        import agent_maps_fetch

        if "GOOGLE_MAPS_API_KEY" in os.environ:
            del os.environ["GOOGLE_MAPS_API_KEY"]

        sys.argv = ["agent_maps_fetch.py", "--query", "Filipino services in Sydney", "--city", "SYDNEY", "--category", "SERVICES"]

        with self.assertRaises(SystemExit) as context:
            await agent_maps_fetch.main()

        self.assertEqual(context.exception.code, 1)



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

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("features.scanning.dedup.check_duplicate", new_callable=AsyncMock)
    @patch("features.scanning.sources.geocoder.geocode_address", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_graphql_push_string_review_converted(
        self, mock_stdout: MagicMock, mock_geocode: AsyncMock, mock_check: AsyncMock, mock_execute: AsyncMock
    ) -> None:
        """Tests that agent_graphql_push.py normalizes string reviews to dicts and pushes successfully."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "New Resto", "category": "RESTAURANT", "city": "SYDNEY", "address": "123 St", "reviews": ["Delicious food!"]}'
        ]

        mock_check.return_value = None
        mock_geocode.return_value = (-33.8688, 151.2093)
        mock_execute.return_value = {"data": {"createListing": {"id": "new-999"}}}

        await agent_graphql_push.main()

        # Check CreateListing variables
        mock_execute.assert_any_call(
            operation_name="CreateListing",
            variables={
                "name": "New Resto",
                "categories": ["RESTAURANT"],
                "city": "SYDNEY",
                "address": "123 St",
                "latitude": -33.8688,
                "longitude": 151.2093,
                "verificationStatus": "UNVERIFIED",
                "descriptionEmbedding": None
            },
        )

        # Verify review call has structured dict format
        mock_execute.assert_any_call(
            "CreateReview",
            {
                "text": "Delicious food!",
                "authorName": "Google Reviewer",
                "rating": 5.0,
                "externalSourceId": "hash_5af76378611dd74ba92902e914baae27",
                "listingId": "new-999"
            }
        )

    @patch("os.path.exists")
    def test_maps_fetch_categories_file_missing(self, mock_exists: MagicMock) -> None:
        """Tests that agent_maps_fetch.load_valid_categories raises FileNotFoundError when category file is missing."""
        import agent_maps_fetch
        mock_exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            agent_maps_fetch.load_valid_categories()

    @patch("os.path.exists")
    async def test_graphql_push_categories_file_missing(self, mock_exists: MagicMock) -> None:
        """Tests that agent_graphql_push.load_valid_categories raises FileNotFoundError when category file is missing."""
        import agent_graphql_push
        mock_exists.return_value = False
        agent_graphql_push._valid_categories_cache = None
        with self.assertRaises(FileNotFoundError):
            await agent_graphql_push.load_valid_categories()

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_maps_fetch_categories_file_corrupted(self, mock_open: MagicMock, mock_exists: MagicMock) -> None:
        """Tests that agent_maps_fetch.load_valid_categories raises exception when category file has corrupted JSON."""
        import agent_maps_fetch
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.read.return_value = "invalid json{"
        mock_open.return_value.__enter__.return_value = mock_file
        with self.assertRaises(json.JSONDecodeError):
            agent_maps_fetch.load_valid_categories()

    @patch("os.path.exists")
    @patch("builtins.open")
    async def test_graphql_push_categories_file_corrupted(self, mock_open: MagicMock, mock_exists: MagicMock) -> None:
        """Tests that agent_graphql_push.load_valid_categories raises exception when category file has corrupted JSON."""
        import agent_graphql_push
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.read.return_value = "invalid json{"
        mock_open.return_value.__enter__.return_value = mock_file
        agent_graphql_push._valid_categories_cache = None
        with self.assertRaises(json.JSONDecodeError):
            await agent_graphql_push.load_valid_categories()

    @patch("os.path.exists")
    @patch("sys.stderr")
    async def test_graphql_push_main_exits_when_categories_file_missing(self, mock_stderr: MagicMock, mock_exists: MagicMock) -> None:
        """Tests that agent_graphql_push.py main() exits with code 1 when categories file is missing."""
        import agent_graphql_push
        mock_exists.return_value = False
        agent_graphql_push._valid_categories_cache = None
        
        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Some Resto", "city": "SYDNEY"}'
        ]
        
        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)

    @patch("os.path.exists")
    @patch("builtins.open")
    @patch("sys.stderr")
    async def test_graphql_push_main_exits_when_categories_file_corrupted(self, mock_stderr: MagicMock, mock_open: MagicMock, mock_exists: MagicMock) -> None:
        """Tests that agent_graphql_push.py main() exits with code 1 when categories file is corrupted."""
        import agent_graphql_push
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.read.return_value = "invalid json{"
        mock_open.return_value.__enter__.return_value = mock_file
        agent_graphql_push._valid_categories_cache = None
        
        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateListing",
            "--variables",
            '{"name": "Some Resto", "city": "SYDNEY"}'
        ]
        
        with self.assertRaises(SystemExit) as cm:
            await agent_graphql_push.main()
        self.assertEqual(cm.exception.code, 1)

    @patch("agent_generate_embeddings.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_agent_generate_embeddings_success(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests that agent_generate_embeddings.py generates embeddings and updates listings."""
        import agent_generate_embeddings

        sys.argv = ["agent_generate_embeddings.py", "--city", "SYDNEY", "--trace-id", "trace-999"]
        
        mock_execute.side_effect = [
            # First call: Query ListListingsMissingEmbedding
            {
                "data": {
                    "listings": [
                        {"id": "listing-1", "name": "Manila Eats", "categories": ["RESTAURANT"], "description": "Pinoy diner"},
                        {"id": "listing-2", "name": "Filipino Services", "categories": ["SERVICES"], "description": ""}
                    ]
                }
            },
            # Second call: UpdateListingData for listing-1
            {"data": {"updateListing": {"id": "listing-1"}}},
            # Third call: UpdateListingData for listing-2
            {"data": {"updateListing": {"id": "listing-2"}}}
        ]

        await agent_generate_embeddings.main()

        # Check that ListListingsMissingEmbedding was called with correct variables
        mock_execute.assert_any_call("ListListingsMissingEmbedding", {"city": "SYDNEY"})
        
        # Check UpdateListingData calls
        mock_execute.assert_any_call("UpdateListingData", {
            "id": "listing-1",
            "descriptionEmbedding": [0.1] * 768
        })
        mock_execute.assert_any_call("UpdateListingData", {
            "id": "listing-2",
            "descriptionEmbedding": [0.1] * 768
        })

        # Check stdout summary
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed = json.loads(combined_output)
        self.assertEqual(parsed["listings_missing"], 2)
        self.assertEqual(parsed["listings_processed"], 2)
        self.assertEqual(parsed["embeddings_generated"], 2)

    @patch("agent_generate_embeddings.execute_graphql_operation", new_callable=AsyncMock)
    @patch("sys.stdout")
    async def test_agent_generate_embeddings_limit(self, mock_stdout: MagicMock, mock_execute: AsyncMock) -> None:
        """Tests that agent_generate_embeddings.py respects --limit flag."""
        import agent_generate_embeddings

        sys.argv = ["agent_generate_embeddings.py", "--city", "SYDNEY", "--limit", "1", "--trace-id", "trace-999"]
        
        mock_execute.side_effect = [
            # First call: Query ListListingsMissingEmbedding
            {
                "data": {
                    "listings": [
                        {"id": "listing-1", "name": "Manila Eats", "categories": ["RESTAURANT"], "description": "Pinoy diner"},
                        {"id": "listing-2", "name": "Filipino Services", "categories": ["SERVICES"], "description": ""}
                    ]
                }
            },
            # Second call: UpdateListingData for listing-1
            {"data": {"updateListing": {"id": "listing-1"}}}
        ]

        await agent_generate_embeddings.main()

        # Check that ListListingsMissingEmbedding was called
        mock_execute.assert_any_call("ListListingsMissingEmbedding", {"city": "SYDNEY"})
        
        # Check UpdateListingData only called for listing-1
        mock_execute.assert_any_call("UpdateListingData", {
            "id": "listing-1",
            "descriptionEmbedding": [0.1] * 768
        })
        # listing-2 should NOT be updated
        for call_args in mock_execute.call_args_list:
            args = call_args.args
            kwargs = call_args.kwargs
            op = kwargs.get("operation_name") or (args[0] if len(args) > 0 else None)
            vars_ = kwargs.get("variables") or (args[1] if len(args) > 1 else None)
            if op == "UpdateListingData" and vars_ and vars_.get("id") == "listing-2":
                self.fail("UpdateListingData called for listing-2 despite limit=1")

        # Check stdout summary
        written_calls = [call.args[0] for call in mock_stdout.write.call_args_list]
        combined_output = "".join(written_calls)
        parsed = json.loads(combined_output)
        self.assertEqual(parsed["listings_missing"], 2)
        self.assertEqual(parsed["listings_processed"], 1)
        self.assertEqual(parsed["embeddings_generated"], 1)

    def test_maps_fetch_format_place_socials_mapping(self) -> None:
        """Tests that agent_maps_fetch.format_place extracts social URLs from websiteUri."""
        import agent_maps_fetch

        place_fb = {
            "id": "mock_place_fb",
            "displayName": {"text": "FB Business"},
            "websiteUri": "https://www.facebook.com/myfbbusiness"
        }
        res_fb = agent_maps_fetch.format_place(place_fb, "Sydney", "RESTAURANT")
        self.assertEqual(res_fb["facebookUrl"], "https://www.facebook.com/myfbbusiness")
        self.assertIsNone(res_fb["instagramUrl"])
        self.assertIsNone(res_fb["tiktokUrl"])

        place_ig = {
            "id": "mock_place_ig",
            "displayName": {"text": "IG Business"},
            "websiteUri": "https://instagram.com/myigbusiness"
        }
        res_ig = agent_maps_fetch.format_place(place_ig, "Sydney", "RESTAURANT")
        self.assertIsNone(res_ig["facebookUrl"])
        self.assertEqual(res_ig["instagramUrl"], "https://instagram.com/myigbusiness")
        self.assertIsNone(res_ig["tiktokUrl"])

        place_tt = {
            "id": "mock_place_tt",
            "displayName": {"text": "TikTok Business"},
            "websiteUri": "https://tiktok.com/@mytiktokbusiness"
        }
        res_tt = agent_maps_fetch.format_place(place_tt, "Sydney", "RESTAURANT")
        self.assertIsNone(res_tt["facebookUrl"])
        self.assertIsNone(res_tt["instagramUrl"])
        self.assertEqual(res_tt["tiktokUrl"], "https://tiktok.com/@mytiktokbusiness")

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    async def test_graphql_push_update_social_urls_merging(self, mock_execute: AsyncMock) -> None:
        """Tests that UpdateListingSocialUrls merges existing DB values to prevent data loss."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "UpdateListingSocialUrls",
            "--variables",
            '{"id": "123", "facebookFollowers": 500}'
        ]

        mock_execute.side_effect = [
            {
                "data": {
                    "listing": {
                        "id": "123",
                        "facebookUrl": "https://www.facebook.com/old",
                        "instagramUrl": "https://www.instagram.com/old",
                        "tiktokUrl": None,
                        "facebookFollowers": 100,
                        "instagramFollowers": None,
                        "tiktokFollowers": None
                    }
                }
            },
            {
                "data": {
                    "updateListingSocialUrls": {"id": "123"}
                }
            }
        ]

        await agent_graphql_push.main()

        mock_execute.assert_any_call(
            operation_name="GetListing",
            variables={"id": "123"}
        )
        mock_execute.assert_any_call(
            operation_name="UpdateListingSocialUrls",
            variables={
                "id": "123",
                "facebookUrl": "https://www.facebook.com/old",
                "instagramUrl": "https://www.instagram.com/old",
                "tiktokUrl": None,
                "facebookFollowers": 500,
                "instagramFollowers": None,
                "tiktokFollowers": None
            }
        )

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    @patch("features.scanning.sources.geocoder.geocode_address", new_callable=AsyncMock)
    async def test_graphql_push_create_event_defaults_and_geocoding(self, mock_geocode: AsyncMock, mock_execute: AsyncMock) -> None:
        """Tests that CreateEvent injects defaults and geocodes coordinates if missing."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateEvent",
            "--variables",
            '{"listingId": "123", "name": "Fiesta", "city": "Sydney", "startDate": "2026-12-25T10:00:00Z", "description": "Fun"}'
        ]

        mock_execute.side_effect = [
            {"data": {"events": []}},
            {"data": {"createEvent": {"id": "new-evt-1"}}}
        ]
        mock_geocode.return_value = (-33.8, 151.2)

        await agent_graphql_push.main()

        mock_geocode.assert_called_once_with("Sydney", "Sydney")
        mock_execute.assert_any_call(
            operation_name="CreateEvent",
            variables={
                "listingId": "123",
                "name": "Fiesta",
                "city": "Sydney",
                "description": "Fun",
                "startDate": "2026-12-25T10:00:00Z",
                "isRecurring": False,
                "verificationStatus": "UNVERIFIED",
                "latitude": -33.8,
                "longitude": 151.2,
                "descriptionEmbedding": None
            }
        )

    @patch("agent_graphql_push.execute_graphql_operation", new_callable=AsyncMock)
    async def test_graphql_push_create_event_deduplication(self, mock_execute: AsyncMock) -> None:
        """Tests that CreateEvent skips insertion and returns duplicate status if same event/day exists."""
        import agent_graphql_push

        sys.argv = [
            "agent_graphql_push.py",
            "--operation",
            "CreateEvent",
            "--variables",
            '{"listingId": "123", "name": "Fiesta", "city": "Sydney", "startDate": "2026-12-25T10:00:00Z"}'
        ]

        mock_execute.return_value = {
            "data": {
                "events": [
                    {
                        "id": "evt-existing",
                        "name": "Fiesta",
                        "startDate": "2026-12-25T12:00:00Z"
                    }
                ]
            }
        }

        with patch("sys.stdout") as mock_stdout:
            await agent_graphql_push.main()

            mock_execute.assert_called_once()
            call_ops = [c.kwargs.get("operation_name") or c.args[0] for c in mock_execute.call_args_list]
            self.assertIn("ListUpcomingEvents", call_ops)
            self.assertNotIn("CreateEvent", call_ops)

            written = "".join([call.args[0] for call in mock_stdout.write.call_args_list])
            parsed = json.loads(written)
            self.assertEqual(parsed["status"], "DUPLICATE")
            self.assertEqual(parsed["existingId"], "evt-existing")






