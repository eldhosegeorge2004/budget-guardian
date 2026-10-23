import httpx
import time
from backend.config import PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, PAYPAL_BASE_URL

_token_cache = {"access_token": None, "expires_at": 0}


def is_paypal_configured() -> bool:
    """Check if valid PayPal credentials have been provided."""
    return bool(
        PAYPAL_CLIENT_ID
        and PAYPAL_CLIENT_SECRET
        and PAYPAL_CLIENT_ID != "your_sandbox_client_id_here"
        and PAYPAL_CLIENT_SECRET != "your_sandbox_client_secret_here"
    )


def get_access_token() -> str:
    """Fetch (or return cached) PayPal OAuth2 access token."""
    if not is_paypal_configured():
        raise RuntimeError("PayPal credentials are not configured. Running in Demo/Sandbox mode.")

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
