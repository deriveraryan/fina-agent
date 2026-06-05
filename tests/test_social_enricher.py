"""Unit tests for the social media URL enrichment module.

All tests run completely offline and use unittest mocks.
"""

import sys
import os
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestSocialEnricher(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for the social media URL enricher."""

    def setUp(self) -> None:
        self.patchers = []
        # Mock BackendObservability to avoid logs pollution
        self.mock_obs = MagicMock()
        obs_patcher = patch("features.shared.observability.BackendObservability", self.mock_obs)
        obs_patcher.start()
        self.patchers.append(obs_patcher)

        # Mock asyncio.sleep to run instantly
        sleep_patcher = patch("asyncio.sleep", new_callable=AsyncMock)
        sleep_patcher.start()
        self.patchers.append(sleep_patcher)

        # Reset rate limiting timestamps
        from features.scanning.sources import social_enricher
        social_enricher._last_google_search_time = 0.0
        social_enricher._last_gemini_request_time = 0.0

    def tearDown(self) -> None:
        for patcher in self.patchers:
            patcher.stop()

    async def test_search_social_url_google_success(self) -> None:
        """Tests search_social_url_google successfully extracts candidate URL using Crawl4AI."""
        from features.scanning.sources import social_enricher

        # Mock Crawl4AI AsyncWebCrawler
        mock_crawler = AsyncMock()
        mock_result = MagicMock()
        mock_result.html = '<a href="https://www.facebook.com/lolasgrill">Facebook page</a>'
        mock_crawler.arun.return_value = mock_result

        with patch("features.scanning.sources.social_enricher._get_crawler", return_value=mock_crawler):
            url = await social_enricher.search_social_url_google("Lola's Grill", "SYDNEY", "facebook")
            self.assertEqual(url, "https://www.facebook.com/lolasgrill/")
            mock_crawler.arun.assert_called_once()

    async def test_search_social_url_google_no_match(self) -> None:
        """Tests search_social_url_google returns None when no URLs matching domain are found."""
        from features.scanning.sources import social_enricher

        mock_crawler = AsyncMock()
        mock_result = MagicMock()
        mock_result.html = '<a href="https://www.instagram.com/lolasgrill">Instagram profile</a>'
        mock_crawler.arun.return_value = mock_result

        with patch("features.scanning.sources.social_enricher._get_crawler", return_value=mock_crawler):
            # Searching for facebook but got instagram
            url = await social_enricher.search_social_url_google("Lola's Grill", "SYDNEY", "facebook")
            self.assertIsNone(url)

    async def test_verify_social_url_match_success(self) -> None:
        """Tests verify_social_url_match returns True when Gemini verifies the match."""
        from features.scanning.sources import social_enricher

        mock_genai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"is_match": true}'
        mock_genai_client.models.generate_content.return_value = mock_response

        # Patch genai.Client
        with patch("features.scanning.sources.social_enricher.genai.Client", return_value=mock_genai_client), \
             patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
            is_match = await social_enricher.verify_social_url_match("Lola's Grill", "SYDNEY", "https://facebook.com/lolasgrill")
            self.assertTrue(is_match)
            mock_genai_client.models.generate_content.assert_called_once()

    async def test_verify_social_url_match_failure(self) -> None:
        """Tests verify_social_url_match returns False when Gemini rejects the match."""
        from features.scanning.sources import social_enricher

        mock_genai_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"is_match": false}'
        mock_genai_client.models.generate_content.return_value = mock_response

        # Patch genai.Client
        with patch("features.scanning.sources.social_enricher.genai.Client", return_value=mock_genai_client), \
             patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key"}):
            is_match = await social_enricher.verify_social_url_match("Lola's Grill", "SYDNEY", "https://facebook.com/wronggrill")
            self.assertFalse(is_match)

    async def test_search_social_url_browser_fallback(self) -> None:
        """Tests search_social_url_browser fallback using browser-use/Playwright Agent."""
        from features.scanning.sources import social_enricher

        mock_agent = MagicMock()
        mock_history = MagicMock()
        mock_history.final_result.return_value = "https://www.facebook.com/lolasgrill"
        mock_agent.run = AsyncMock(return_value=mock_history)

        mock_browser = MagicMock()
        mock_browser.new_context = AsyncMock()
        mock_browser.close = AsyncMock()
        mock_browser_class = MagicMock(return_value=mock_browser)

        with patch("sys.modules", sys.modules):
            sys.modules["browser_use"].Agent = MagicMock(return_value=mock_agent)
            sys.modules["browser_use.browser.browser"].Browser = mock_browser_class
            sys.modules["langchain_google_genai"].ChatGoogleGenerativeAI = MagicMock()

            url = await social_enricher.search_social_url_browser("Lola's Grill", "SYDNEY", "facebook")
            self.assertEqual(url, "https://www.facebook.com/lolasgrill")

    async def test_enrich_listing_social_orchestration(self) -> None:
        """Tests enrich_listing_social orchestrates search, fallback, and verification."""
        from features.scanning.sources import social_enricher

        listing = {
            "id": "uuid-123",
            "name": "Lola's Grill",
            "city": "SYDNEY",
            "facebookUrl": None,
            "instagramUrl": None,
            "tiktokUrl": None
        }

        # Mock Google search to return facebook URL, Instagram returns nothing
        async def mock_search_google(name, city, platform):
            if platform == "facebook":
                return "https://facebook.com/lolasgrill"
            return None

        # Mock browser fallback to return Instagram URL
        async def mock_search_browser(name, city, platform):
            if platform == "instagram":
                return "https://instagram.com/lolasgrill"
            return None

        # Mock match verification to approve all
        async def mock_verify(name, city, url):
            return True

        with patch("features.scanning.sources.social_enricher.search_social_url_google", side_effect=mock_search_google), \
             patch("features.scanning.sources.social_enricher.search_social_url_browser", side_effect=mock_search_browser), \
             patch("features.scanning.sources.social_enricher.verify_social_url_match", side_effect=mock_verify):
            
            result = await social_enricher.enrich_listing_social(listing, ["facebook", "instagram"])
            self.assertEqual(result.get("facebookUrl"), "https://facebook.com/lolasgrill")
            self.assertEqual(result.get("instagramUrl"), "https://instagram.com/lolasgrill")
            self.assertIsNone(result.get("tiktokUrl"))

    async def test_close_crawler_cleanup(self) -> None:
        """Tests close_crawler cleanly exits AsyncWebCrawler."""
        from features.scanning.sources import social_enricher

        mock_crawler = AsyncMock()
        social_enricher._crawler = mock_crawler

        await social_enricher.close_crawler()
        mock_crawler.__aexit__.assert_called_once()
        self.assertIsNone(social_enricher._crawler)

    @classmethod
    def setUpClass(cls) -> None:
        cls._orig_modules = {}
        for key in [
            "crawl4ai",
            "crawl4ai.extraction_strategy",
            "browser_use",
            "browser_use.browser",
            "browser_use.browser.browser",
            "browser_use.browser.context",
            "langchain_google_genai",
        ]:
            if key in sys.modules:
                cls._orig_modules[key] = sys.modules[key]
            sys.modules[key] = MagicMock()

    @classmethod
    def tearDownClass(cls) -> None:
        # Clean up dynamically mocked modules to prevent cross-test pollution
        for key in [
            "crawl4ai",
            "crawl4ai.extraction_strategy",
            "browser_use",
            "browser_use.browser",
            "browser_use.browser.browser",
            "browser_use.browser.context",
            "langchain_google_genai",
        ]:
            if key in cls._orig_modules:
                sys.modules[key] = cls._orig_modules[key]
            else:
                sys.modules.pop(key, None)


if __name__ == "__main__":
    unittest.main()
