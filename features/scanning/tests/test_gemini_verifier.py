"""Unit tests for the Gemini-powered authentic Filipino affiliation verifier.

Runs completely offline using unittest mocks.
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from features.scanning.sources.maps_scanner import verify_filipino_affiliation


class TestGeminiVerifier(unittest.IsolatedAsyncioTestCase):
    """Offline unit test suite for the Gemini affiliation classification engine."""

    async def test_verify_filipino_affiliation_heuristics(self) -> None:
        """Tests that verify_filipino_affiliation returns correct values using keyword heuristics fallback when key is missing."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=True):
            # Verify various words that trigger True
            self.assertTrue(await verify_filipino_affiliation("Lola's Pinoy Grill", [], "", []))
            self.assertTrue(await verify_filipino_affiliation("Manila Bakery", [], "", []))
            self.assertTrue(await verify_filipino_affiliation("Sari-Sari Store Perth", [], "", []))
            # Verify words that trigger False
            self.assertFalse(await verify_filipino_affiliation("General Pizza Restaurant", [], "", []))

    @patch("google.genai.Client")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "fake-api-key"})
    async def test_verify_filipino_affiliation_gemini_success(self, mock_client_class: MagicMock) -> None:
        """Tests that a successful JSON response from Gemini is parsed and returns correct boolean values."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"is_filipino": true}'
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = await verify_filipino_affiliation("Manila Bistro", ["restaurant"], "A nice restaurant", ["Great food!"])
        self.assertTrue(result)
        mock_client.models.generate_content.assert_called_once()

    @patch("google.genai.Client")
    @patch("asyncio.sleep")
    @patch.dict("os.environ", {"GEMINI_API_KEY": "fake-api-key"})
    async def test_verify_filipino_affiliation_rate_limiting_429_retry(self, mock_sleep: AsyncMock, mock_client_class: MagicMock) -> None:
        """Tests that a 429 rate limit exception triggers backoff sleeps and successful retry attempt."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"is_filipino": true}'
        
        # Raise 429 on first try, then return success on second try
        mock_client.models.generate_content.side_effect = [
            RuntimeError("RESOURCE_EXHAUSTED: Please retry in 5.0s"),
            mock_response
        ]
        mock_client_class.return_value = mock_client

        result = await verify_filipino_affiliation("Manila Bistro", ["restaurant"], "A nice restaurant", ["Great food!"])
        self.assertTrue(result)
        self.assertEqual(mock_client.models.generate_content.call_count, 2)
        
        # Verify that the 429 backoff sleep (5.5s) was executed
        sleep_args = [call_args[0][0] for call_args in mock_sleep.call_args_list if call_args[0]]
        self.assertTrue(any(arg >= 5.5 for arg in sleep_args))


if __name__ == "__main__":
    unittest.main()
