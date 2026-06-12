import re
import json
from typing import Union
from features.shared.observability import BackendObservability

# Pre-compiled regular expressions for performance
RE_CLEAN_FOLLOWERS = re.compile(r"\s*FOLLOWERS?", re.IGNORECASE)
RE_REHYDRATION = re.compile(
    r'<script\s+id="__UNIVERSAL_DATA_FOR_REHYDRATION__"\s+type="application/json">(.*?)</script>',
    re.DOTALL
)
RE_SIGI_STATE = re.compile(
    r'<script\s+id="SIGI_STATE"\s+type="application/json">(.*?)</script>',
    re.DOTALL
)
RE_DOM_FALLBACK = re.compile(r'data-e2e="followers-count"[^>]*>([^<]+)<')
RE_META_DESC = re.compile(
    r'<meta\s+(?:name|property)="[^"]*description"\s+content="([^"]*)"',
    re.IGNORECASE
)
RE_FOLLOWERS_PATTERN = re.compile(r"([\d,.]+[KkMm]?)\s*Followers", re.IGNORECASE)


def clean_follower_count(val_str: str) -> Union[int, None]:
    """Cleans a string representation of follower count and converts to integer.

    e.g. "1.5K" -> 1500, "2.4M" -> 2400000, "500" -> 500
    """
    if not val_str:
        return None
    val_str = val_str.strip().upper()

    # Strip any trailing 'FOLLOWERS' text, spaces, or commas
    val_str = RE_CLEAN_FOLLOWERS.sub("", val_str)
    val_str = val_str.replace(",", "").strip()

    if not val_str:
        return None

    try:
        if "M" in val_str:
            num = float(val_str.replace("M", "").strip())
            return int(num * 1000000)
        elif "K" in val_str:
            num = float(val_str.replace("K", "").strip())
            return int(num * 1000)
        else:
            return int(float(val_str))
    except (ValueError, TypeError):
        return None


def parse_tiktok_followers(html_content: Union[str, None]) -> Union[int, None]:
    """Extracts the follower count from a TikTok profile's HTML content.

    Tries rehydration data, SIGI_STATE, meta tags, and DOM fallback.
    """
    if not html_content:
        return None

    # 1. Try __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON block
    rehydration_match = RE_REHYDRATION.search(html_content)
    if rehydration_match:
        try:
            data = json.loads(rehydration_match.group(1).strip())
            scope = data.get("__DEFAULT_SCOPE__", {})
            user_detail = scope.get("webapp.user-detail", {})
            stats = user_detail.get("userInfo", {}).get("stats", {})
            followers = stats.get("followerCount")
            if isinstance(followers, (int, float)):
                return int(followers)
        except Exception as exc:
            BackendObservability.debug(
                f"Failed to parse __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON: {exc}"
            )

    # 2. Try SIGI_STATE JSON block
    sigi_match = RE_SIGI_STATE.search(html_content)
    if sigi_match:
        try:
            data = json.loads(sigi_match.group(1).strip())
            users = data.get("UserModule", {}).get("users", {})
            for user in users.values():
                followers = user.get("stats", {}).get("followerCount")
                if isinstance(followers, (int, float)):
                    return int(followers)
        except Exception as exc:
            BackendObservability.debug(
                f"Failed to parse SIGI_STATE JSON: {exc}"
            )

    # 3. Try DOM fallback pattern data-e2e="followers-count"
    dom_match = RE_DOM_FALLBACK.search(html_content)
    if dom_match:
        followers = clean_follower_count(dom_match.group(1))
        if followers is not None:
            return followers

    # 4. Try Meta Description/OG Description content
    meta_matches = RE_META_DESC.findall(html_content)
    for content in meta_matches:
        follower_match = RE_FOLLOWERS_PATTERN.search(content)
        if follower_match:
            followers = clean_follower_count(follower_match.group(1))
            if followers is not None:
                return followers

    return None
