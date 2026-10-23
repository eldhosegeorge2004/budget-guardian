import httpx
import time
from backend.config import PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_BASE_URL

_token_cache = {"access_token": None, "expires_at": 0}


def get_access_token() -> str:
    """Fetch (or return cached) PayPal OAuth2 access token."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 30:
        return _token_cache["access_token"]

    url = f"{PAYPAL_BASE_URL}/v1/oauth2/token"
    response = httpx.post(
        url,
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    _token_cache["access_token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 3600)
    return _token_cache["access_token"]


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }
