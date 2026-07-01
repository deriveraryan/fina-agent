"""Unit tests for Fina listing normalization, merging, and database-level exact/semantic deduplication.

Runs completely offline using unittest mocks.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from features.scanning.dedup import normalize_name, merge_listing_data, check_duplicate, fuzzy_name_match


class TestDeduplication(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for listing deduplication and normalization."""

    def test_normalize_name(self) -> None:
        """Tests that business names are normalized correctly by removing suffixes and extra spaces."""
        self.assertEqual(normalize_name("Gold Ribbon Bakery Pty Ltd"), "gold ribbon bakery")
        self.assertEqual(normalize_name("Lola's Cafe Pty. Ltd."), "lola's cafe")
        self.assertEqual(normalize_name("Manila Grocery Inc."), "manila grocery")
        self.assertEqual(normalize_name("  Sari-Sari Store   "), "sari-sari store")
        self.assertEqual(normalize_name("Nene's Kitchen LLC"), "nene's kitchen")
        self.assertEqual(normalize_name(""), "")

    def test_merge_listing_data(self) -> None:
        """Tests that new non-empty listing fields overwrite existing database fields, while empty/null fields preserve them."""
        existing = {
            "name": "Manila Bistro",
            "categories": ["RESTAURANT"],
            "city": "SYDNEY",
            "address": "123 Pitt St",
            "phone": None,
            "website": "",
            "imageUrl": "http://existing.img",
        }
        new_data = {
            "name": "Manila Bistro Pty Ltd",
            "categories": ["RESTAURANT", "CAFE"],
            "phone": "0400111222",
            "website": "https://manilabistro.com.au",
            "imageUrl": "http://new.img",
        }

        merged = merge_listing_data(existing, new_data)

        self.assertEqual(merged["name"], "Manila Bistro Pty Ltd")  # Overwritten by non-empty new name
        self.assertEqual(merged["phone"], "0400111222")  # Filled null
        self.assertEqual(merged["website"], "https://manilabistro.com.au")  # Filled empty string
        self.assertEqual(merged["imageUrl"], "http://new.img")  # Overwritten by non-empty new imageUrl
        self.assertEqual(sorted(merged["categories"]), ["CAFE", "RESTAURANT"])  # Merged categories

        # Test that empty or null incoming fields do NOT overwrite existing non-empty fields
        existing2 = {
            "name": "Manila Bistro",
            "categories": ["RESTAURANT"],
            "city": "SYDNEY",
            "phone": "0299999999",
            "facebookFollowers": 1500,
        }
        new_data2 = {
            "name": "",
            "categories": [],
            "phone": None,
            "facebookFollowers": None,
        }
        merged2 = merge_listing_data(existing2, new_data2)
        self.assertEqual(merged2["name"], "Manila Bistro")
        self.assertEqual(merged2["categories"], ["RESTAURANT"])
        self.assertEqual(merged2["phone"], "0299999999")
        self.assertEqual(merged2["facebookFollowers"], 1500)

    def test_deduplicate_batch(self) -> None:
        """Tests that deduplicate_batch merges listings by overwriting sequentially."""
        from features.scanning.dedup import deduplicate_batch
        
        batch = [
            {"name": "Lola's Kitchen", "sourceUrl": None, "categories": ["RESTAURANT"], "city": "SYDNEY"},
            {"name": "Lola's Kitchen Pty Ltd", "sourceUrl": None, "categories": ["CAFE"]},  # Merge by norm_name
            {"name": "Lola's Kitchen", "sourceUrl": None, "categories": ["SHOP"]}, # Merge by norm_name
            {"name": "Unique Place", "sourceUrl": "url3", "categories": ["CHURCH"]}
        ]
        
        deduped = deduplicate_batch(batch)
        self.assertEqual(len(deduped), 2)
        
        # Check Lola's Kitchen merged correctly by overwriting categories sequentially
        lola = next(item for item in deduped if item["name"] == "Lola's Kitchen")
        self.assertEqual(lola["categories"], ["SHOP"])

        # Check Unique Place exists
        unique = next(item for item in deduped if item["name"] == "Unique Place")
        self.assertEqual(unique["categories"], ["CHURCH"])

    @patch("features.shared.graphql_client.execute_graphql_operation")
    async def test_check_duplicate_exact_match(self, mock_execute: AsyncMock) -> None:
        """Tests that check_duplicate correctly identifies duplicates via exact normalized name match."""
        # Mock ListCityListings response
        mock_execute.return_value = {
            "data": {
                "listings": [
                    {
                        "id": "abc-123",
                        "name": "Lola's Kitchen",
                        "city": "SYDNEY",
                    }
                ]
            }
        }

        result = await check_duplicate("Lola's Kitchen Pty Ltd", "SYDNEY")

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "abc-123")
        mock_execute.assert_called_once_with(
            operation_name="ListAdminListings",
            variables={
                "city": "SYDNEY",
                "limit": 2000,
                "verificationStatuses": ["VERIFIED", "UNVERIFIED"]
            },
        )

    @patch("features.shared.embeddings.get_embedding")
    @patch("features.shared.graphql_client.execute_graphql_operation")
    async def test_check_duplicate_semantic_match(self, mock_execute: AsyncMock, mock_get_embedding: MagicMock) -> None:
        """Tests that check_duplicate falls back to semantic cosine similarity when exact match fails."""
        mock_get_embedding.return_value = [0.1] * 768
        # Mock ListCityListings response
        mock_execute.side_effect = [
            {"data": {"listings": []}},  # ListCityListings
            {
                "data": {
                    "listings_descriptionEmbedding_similarity": [
                        {
                            "id": "def-456",
                            "name": "Manila Bistro",
                            "city": "SYDNEY",
                        }
                    ]
                }
            },  # SemanticSearchListings
        ]

        result = await check_duplicate(
            "Manila Bistro",
            "SYDNEY",
            description="A cozy Filipino diner serving adobo",
            categories=["RESTAURANT"],
            generate_embeddings=True,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "def-456")
        self.assertEqual(mock_execute.call_count, 2)
        mock_execute.assert_any_call(
            operation_name="SemanticSearchListings",
            variables={
                "city": "SYDNEY",
                "queryEmbedding": [0.1] * 768
            }
        )

    @patch("features.shared.embeddings.get_embedding")
    @patch("features.shared.graphql_client.execute_graphql_operation")
    async def test_check_duplicate_semantic_null_response(self, mock_execute: AsyncMock, mock_get_embedding: MagicMock) -> None:
        """Tests that check_duplicate handles None/null semantic search responses gracefully without crashing."""
        mock_get_embedding.return_value = [0.1] * 768
        mock_execute.side_effect = [
            {"data": {"listings": []}},  # ListCityListings
            {"data": {"listings_descriptionEmbedding_similarity": None}},  # SemanticSearchListings returning null
        ]

        result = await check_duplicate(
            "Manila Bistro",
            "SYDNEY",
            description="A cozy Filipino diner serving adobo",
            categories=["RESTAURANT"],
            generate_embeddings=True,
        )

        self.assertIsNone(result)
        self.assertEqual(mock_execute.call_count, 2)

    def test_fuzzy_name_match_concatenated_words(self) -> None:
        """CJMigration vs CJ Migration — the original root cause duplicate."""
        is_match, score = fuzzy_name_match("CJ Migration", "CJMigration")
        self.assertTrue(is_match)
        self.assertGreater(score, 85)

    def test_fuzzy_name_match_with_hyphen_spacing(self) -> None:
        """Jollibee Parramatta vs Jollibee - Parramatta."""
        is_match, score = fuzzy_name_match("Jollibee Parramatta", "Jollibee - Parramatta")
        self.assertTrue(is_match)
        self.assertGreater(score, 85)

    def test_fuzzy_name_match_subset_name(self) -> None:
        """Pinoy Stop vs Pinoy Stop Ashfield — subset should match."""
        is_match, score = fuzzy_name_match("Pinoy Stop", "Pinoy Stop Ashfield")
        self.assertTrue(is_match)
        self.assertGreater(score, 85)

    def test_fuzzy_name_match_completely_different(self) -> None:
        """Completely different businesses should not match."""
        is_match, score = fuzzy_name_match("Manila Grill", "Tindahan Filipino")
        self.assertFalse(is_match)
        self.assertLess(score, 85)

    def test_fuzzy_name_match_empty_inputs(self) -> None:
        """Empty or None-like inputs should not match."""
        is_match, score = fuzzy_name_match("", "CJ Migration")
        self.assertFalse(is_match)
        self.assertEqual(score, 0.0)

        is_match2, score2 = fuzzy_name_match("CJ Migration", "")
        self.assertFalse(is_match2)
        self.assertEqual(score2, 0.0)

    def test_fuzzy_name_match_corporate_suffix_stripped(self) -> None:
        """Corporate suffixes should be stripped before fuzzy comparison."""
        is_match, score = fuzzy_name_match("Manila Grill Pty Ltd", "Manila Grill")
        self.assertTrue(is_match)
        self.assertGreater(score, 95)

    @patch("features.shared.embeddings.get_embedding")
    @patch("features.shared.graphql_client.execute_graphql_operation")
    async def test_check_duplicate_semantic_fuzzy_match(self, mock_execute: AsyncMock, mock_get_embedding: MagicMock) -> None:
        """Tests that check_duplicate catches 'CJMigration' vs 'CJ Migration' via fuzzy match in semantic tier."""
        mock_get_embedding.return_value = [0.1] * 768
        mock_execute.side_effect = [
            {"data": {"listings": []}},  # ListAdminListings — no exact match
            {
                "data": {
                    "listings_descriptionEmbedding_similarity": [
                        {
                            "id": "dup-fuzzy-1",
                            "name": "CJ Migration",
                            "city": "SYDNEY",
                        }
                    ]
                }
            },  # SemanticSearchListings
        ]

        result = await check_duplicate(
            "CJMigration",
            "SYDNEY",
            description="Migration services",
            categories=["SERVICES"],
            generate_embeddings=True,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "dup-fuzzy-1")


if __name__ == "__main__":
    unittest.main()
