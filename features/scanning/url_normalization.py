"""Utility functions to normalize and validate social media URLs for Fina listings.
"""

import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import httpx
from features.shared.observability import BackendObservability

# Global AsyncClient instance for connection reuse
_client: httpx.AsyncClient | None = None

def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient()
    return _client


def normalize_facebook_url(url: str) -> str | None:
    """Normalizes and validates Facebook profile/page URLs.
    
    Standardizes domain, ensures HTTPS, removes tracking query parameters,
    and strips trailing slashes. Returns None if invalid.
    """
    if not url:
        return None
        
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return None
        
    netloc = parsed.netloc.lower()
    if not any(domain in netloc for domain in ("facebook.com", "fb.com", "messenger.com")):
        return None
        
    # Standardize domain and scheme
    std_netloc = "www.facebook.com"
    scheme = "https"
    
    path = parsed.path.rstrip("/")
    query = ""
    
    # Handle profile.php?id=... format
    if "profile.php" in path:
        q_params = parse_qs(parsed.query)
        profile_ids = q_params.get("id")
        if profile_ids:
            query = urlencode({"id": profile_ids[0]})
        else:
            return None
            
    # Reassemble URL
    normalized = urlunparse((scheme, std_netloc, path, parsed.params, query, parsed.fragment))
    return normalized


def normalize_instagram_url(url: str, trace_id: str | None = None) -> str | None:
    """Normalizes and validates Instagram profile URLs.
    
    Standardizes domain, converts handle to lowercase, strips tracking parameters,
    and rejects post/reel URLs. Returns None if invalid.
    """
    if not url:
        return None
        
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return None
        
    netloc = parsed.netloc.lower()
    if not any(domain in netloc for domain in ("instagram.com", "instagr.am")):
        return None
        
    # Standardize domain and scheme
    std_netloc = "www.instagram.com"
    scheme = "https"
    
    path = parsed.path.rstrip("/")
    
    # Reject post, reel, and reels URLs (they do not contain user handles)
    path_parts = [p for p in path.split("/") if p]
    if not path_parts:
        return None
        
    first_segment = path_parts[0].lower()
    if first_segment in ("p", "reel", "reels", "stories", "tv"):
        BackendObservability.warning(f"Rejected Instagram content URL instead of profile page: {url}", conversation_id=trace_id)
        return None
        
    # Handle casing (usernames are case-insensitive, convert to lowercase)
    path_parts[0] = path_parts[0].lower()
    normalized_path = "/" + "/".join(path_parts)
    
    normalized = urlunparse((scheme, std_netloc, normalized_path, parsed.params, "", parsed.fragment))
    return normalized


def normalize_tiktok_url(url: str) -> str | None:
    """Synchronous normalization for standard TikTok URLs.
    
    Ensures @ prefix, standardizes domain, removes tracking query parameters,
    and extracts handles from video URLs. Returns None for shortened redirect URLs
    or invalid patterns.
    """
    if not url:
        return None
        
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return None
        
    netloc = parsed.netloc.lower()
    
    # Shortened domains must be handled via the async method
    if netloc in ("vm.tiktok.com", "vt.tiktok.com"):
        return None
        
    if "tiktok.com" not in netloc:
        return None
        
    std_netloc = "www.tiktok.com"
    scheme = "https"
    
    path = parsed.path.rstrip("/")
    path_parts = [p for p in path.split("/") if p]
    if not path_parts:
        return None
        
    username = path_parts[0]
    
    # Handle video/post links: /@username/video/123 -> username is @username
    # If the username doesn't start with @, prepend it
    if not username.startswith("@"):
        username = "@" + username
        
    normalized_path = f"/{username}"
    
    normalized = urlunparse((scheme, std_netloc, normalized_path, parsed.params, "", parsed.fragment))
    return normalized


async def normalize_tiktok_url_async(url: str, trace_id: str | None = None) -> str | None:
    """Asynchronously normalizes TikTok URLs.
    
    Follows redirects for shortened domains (vm.tiktok.com, vt.tiktok.com)
    and then standardizes the resolved canonical profile URL.
    """
    if not url:
        return None
        
    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return None
        
    netloc = parsed.netloc.lower()
    if netloc in ("vm.tiktok.com", "vt.tiktok.com"):
        BackendObservability.trace(f"Resolving shortened TikTok URL: {url}", conversation_id=trace_id)
        try:
            client = _get_client()
            # Use a HEAD request with a short timeout of 5 seconds to get the final redirected URL
            response = await client.head(url, timeout=5.0, follow_redirects=True)
            resolved_url = str(response.url)
            BackendObservability.info(f"Resolved shortened TikTok URL to: {resolved_url}", conversation_id=trace_id)
            return normalize_tiktok_url(resolved_url)
        except Exception as exc:
            BackendObservability.warning(f"Failed to resolve shortened TikTok URL {url}: {exc}", conversation_id=trace_id)
            return None
            
    return normalize_tiktok_url(url)


async def normalize_listing_socials(item_dict: dict, trace_id: str | None = None) -> dict:
    """Iterates through and normalizes facebookUrl, instagramUrl, and tiktokUrl keys in-place/in-copy."""
    result = dict(item_dict)
    
    fb = result.get("facebookUrl")
    if fb:
        result["facebookUrl"] = normalize_facebook_url(fb)
        if not result["facebookUrl"]:
            BackendObservability.warning(f"Stripped invalid Facebook URL: {fb}", conversation_id=trace_id)
            
    ig = result.get("instagramUrl")
    if ig:
        result["instagramUrl"] = normalize_instagram_url(ig, trace_id=trace_id)
        if not result["instagramUrl"]:
            BackendObservability.warning(f"Stripped invalid Instagram URL: {ig}", conversation_id=trace_id)
            
    tt = result.get("tiktokUrl")
    if tt:
        result["tiktokUrl"] = await normalize_tiktok_url_async(tt, trace_id=trace_id)
        if not result["tiktokUrl"]:
            BackendObservability.warning(f"Stripped invalid TikTok URL: {tt}", conversation_id=trace_id)
            
    return result
