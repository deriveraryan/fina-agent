import unittest
from features.scanning.tiktok_parser import parse_tiktok_followers


class TestTiktokParser(unittest.TestCase):
    def test_parse_universal_data_for_rehydration(self) -> None:
        html = """
        <html>
          <body>
            <script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">
            {
              "__DEFAULT_SCOPE__": {
                "webapp.user-detail": {
                  "userInfo": {
                    "stats": {
                      "followerCount": 42500
                    }
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """
        self.assertEqual(parse_tiktok_followers(html), 42500)

    def test_parse_sigi_state(self) -> None:
        html = """
        <html>
          <body>
            <script id="SIGI_STATE" type="application/json">
            {
              "UserModule": {
                "users": {
                  "someuser": {
                    "stats": {
                      "followerCount": 8900
                    }
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """
        self.assertEqual(parse_tiktok_followers(html), 8900)

    def test_parse_meta_description_millions(self) -> None:
        html = """
        <html>
          <head>
            <meta name="description" content="someuser on TikTok. 1.2M Followers, 560 Following, 12.3M Likes.">
          </head>
        </html>
        """
        self.assertEqual(parse_tiktok_followers(html), 1200000)

    def test_parse_meta_og_description_thousands(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:description" content="someuser (@someuser) on TikTok | 450.5K Followers. 120 Likes.">
          </head>
        </html>
        """
        self.assertEqual(parse_tiktok_followers(html), 450500)

    def test_parse_meta_og_description_simple(self) -> None:
        html = """
        <html>
          <head>
            <meta property="og:description" content="someuser on TikTok | 950 Followers. 120 Likes.">
          </head>
        </html>
        """
        self.assertEqual(parse_tiktok_followers(html), 950)

    def test_parse_dom_selector_data_e2e(self) -> None:
        html = """
        <html>
          <body>
            <strong data-e2e="followers-count">3.2K</strong>
          </body>
        </html>
        """
        self.assertEqual(parse_tiktok_followers(html), 3200)

    def test_parse_invalid_or_missing(self) -> None:
        self.assertIsNone(parse_tiktok_followers("<html><body>No followers here</body></html>"))
        self.assertIsNone(parse_tiktok_followers(""))
        self.assertIsNone(parse_tiktok_followers(None))
