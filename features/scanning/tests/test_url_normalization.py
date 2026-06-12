import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import httpx

from features.scanning.url_normalization import (
    normalize_facebook_url,
    normalize_instagram_url,
    normalize_tiktok_url,
    normalize_tiktok_url_async,
    normalize_listing_socials,
)


class TestUrlNormalization(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        import features.scanning.url_normalization as url_norm
        url_norm._client = None

    def tearDown(self) -> None:
        import features.scanning.url_normalization as url_norm
        url_norm._client = None

    def test_normalize_facebook_url(self) -> None:
        # Standard profiles
        self.assertEqual(
            normalize_facebook_url("https://www.facebook.com/mypage"),
            "https://www.facebook.com/mypage",
        )
        self.assertEqual(
            normalize_facebook_url("http://facebook.com/mypage/"),
            "https://www.facebook.com/mypage",
        )
        self.assertEqual(
            normalize_facebook_url("https://facebook.com/mypage?ref=bookmarks"),
            "https://www.facebook.com/mypage",
        )
        
        # Profile ID format
        self.assertEqual(
            normalize_facebook_url("https://www.facebook.com/profile.php?id=100083162"),
            "https://www.facebook.com/profile.php?id=100083162",
        )
        self.assertEqual(
            normalize_facebook_url("https://www.facebook.com/profile.php?id=100083162&ref=bookmarks"),
            "https://www.facebook.com/profile.php?id=100083162",
        )
        
        # Subpaths / Groups / etc.
        self.assertEqual(
            normalize_facebook_url("https://www.facebook.com/groups/mygroup"),
            "https://www.facebook.com/groups/mygroup",
        )
        
        # Invalid / Malformed / Non-FB URLs
        self.assertIsNone(normalize_facebook_url("https://google.com"))
        self.assertIsNone(normalize_facebook_url(""))
        self.assertIsNone(normalize_facebook_url(None))

    def test_normalize_instagram_url(self) -> None:
        # Standard profiles
        self.assertEqual(
            normalize_instagram_url("https://www.instagram.com/My_Handle"),
            "https://www.instagram.com/my_handle",
        )
        self.assertEqual(
            normalize_instagram_url("http://instagram.com/my_handle/"),
            "https://www.instagram.com/my_handle",
        )
        self.assertEqual(
            normalize_instagram_url("https://instagram.com/my_handle?igsh=abc"),
            "https://www.instagram.com/my_handle",
        )
        
        # Rejection of post/reel URLs (these don't have handles)
        self.assertIsNone(normalize_instagram_url("https://www.instagram.com/p/C3j2X/"))
        self.assertIsNone(normalize_instagram_url("https://instagram.com/reel/C3j2X/?igsh=abc"))
        self.assertIsNone(normalize_instagram_url("https://www.instagram.com/reels/C3j2X"))
        
        # Invalid / Non-IG URLs
        self.assertIsNone(normalize_instagram_url("https://facebook.com/myhandle"))
        self.assertIsNone(normalize_instagram_url(""))
        self.assertIsNone(normalize_instagram_url(None))

    def test_normalize_tiktok_url_sync(self) -> None:
        # Standard profiles with @
        self.assertEqual(
            normalize_tiktok_url("https://www.tiktok.com/@myhandle"),
            "https://www.tiktok.com/@myhandle",
        )
        self.assertEqual(
            normalize_tiktok_url("http://tiktok.com/@myhandle/"),
            "https://www.tiktok.com/@myhandle",
        )
        self.assertEqual(
            normalize_tiktok_url("https://tiktok.com/@myhandle?lang=en"),
            "https://www.tiktok.com/@myhandle",
        )
        
        # Missing @ sign
        self.assertEqual(
            normalize_tiktok_url("https://www.tiktok.com/myhandle"),
            "https://www.tiktok.com/@myhandle",
        )
        
        # Extraction of handle from video URLs
        self.assertEqual(
            normalize_tiktok_url("https://www.tiktok.com/@myhandle/video/1234567890"),
            "https://www.tiktok.com/@myhandle",
        )
        self.assertEqual(
            normalize_tiktok_url("https://tiktok.com/myhandle/video/1234567890"),
            "https://www.tiktok.com/@myhandle",
        )
        
        # Invalid / Shortened (which requires async)
        self.assertIsNone(normalize_tiktok_url("https://vt.tiktok.com/ZMy12345/"))
        self.assertIsNone(normalize_tiktok_url("https://google.com"))
        self.assertIsNone(normalize_tiktok_url(""))
        self.assertIsNone(normalize_tiktok_url(None))

    @patch("httpx.AsyncClient")
    async def test_normalize_tiktok_url_async_redirect(self, mock_client_cls: MagicMock) -> None:
        # Set up mock AsyncClient response following redirects
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        
        # Since standard httpx client follow-redirects goes directly to the destination,
        # we can mock get/head returning the final response or the intermediate redirect response.
        # Let's mock a successful head response that has the final URL on `response.url`
        mock_final_response = MagicMock()
        mock_final_response.url = httpx.URL("https://www.tiktok.com/@resolvedhandle?tracker=1")
        mock_final_response.status_code = 200
        
        mock_client.head.return_value = mock_final_response
        
        result = await normalize_tiktok_url_async("https://vt.tiktok.com/ZMy12345/")
        self.assertEqual(result, "https://www.tiktok.com/@resolvedhandle")
        mock_client.head.assert_called_once()
        
    @patch("httpx.AsyncClient")
    async def test_normalize_tiktok_url_async_redirect_failure(self, mock_client_cls: MagicMock) -> None:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        mock_client.head.side_effect = httpx.RequestError("Network connection failed")
        
        # Should fallback to None but log warning, without throwing error
        result = await normalize_tiktok_url_async("https://vt.tiktok.com/ZMy12345/")
        self.assertIsNone(result)

    async def test_normalize_listing_socials(self) -> None:
        item = {
            "name": "Test Place",
            "facebookUrl": "https://facebook.com/TestPage/?ref=bookmarks",
            "instagramUrl": "https://www.instagram.com/reel/C3j2X/",  # Invalid, should become None
            "tiktokUrl": "https://tiktok.com/test_user",  # missing @, should be normalized
        }
        
        normalized = await normalize_listing_socials(item)
        self.assertEqual(normalized["facebookUrl"], "https://www.facebook.com/TestPage")
        self.assertIsNone(normalized["instagramUrl"])
        self.assertEqual(normalized["tiktokUrl"], "https://www.tiktok.com/@test_user")
        self.assertEqual(normalized["name"], "Test Place")
