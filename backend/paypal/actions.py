import json
import httpx
from typing import Optional
from backend.config import PAYPAL_BASE_URL
from backend.paypal.auth import get_headers


def send_payout(
    recipient_email: str,
    amount: float,
    currency: str = "USD",
    note: str = "Budget Guardian automated payout",
    sender_item_id: str = "BG_AUTO_001",
) -> dict:
    """
    Send a PayPal payout to a single recipient.
    Uses the PayPal Payouts API (sandbox).
    """
    url = f"{PAYPAL_BASE_URL}/v1/payments/payouts"
    payload = {
        "sender_batch_header": {
            "sender_batch_id": sender_item_id,
            "email_subject": "You have a payment from Budget Guardian",
            "email_message": note,
        },
        "items": [
            {
                "recipient_type": "EMAIL",
                "amount": {"value": f"{amount:.2f}", "currency": currency},
                "note": note,
                "receiver": recipient_email,
                "sender_item_id": sender_item_id,
            }
        ],
    }
    response = httpx.post(url, headers=get_headers(), json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def get_payout_status(payout_batch_id: str) -> dict:
    """Check the status of a payout batch."""
    url = f"{PAYPAL_BASE_URL}/v1/payments/payouts/{payout_batch_id}"
    response = httpx.get(url, headers=get_headers(), timeout=15)
    response.raise_for_status()
    return response.json()
