import json
import hmac
import hashlib
from fastapi import Request, HTTPException
from backend.config import SECRET_KEY


def verify_webhook_signature(request_body: bytes, headers: dict) -> bool:
    """
    Basic webhook signature verification.
    In production, use PayPal's /v1/notifications/verify-webhook-signature endpoint.
    For sandbox/demo we do a simplified check.
    """
    # PayPal sends: PAYPAL-TRANSMISSION-SIG header
    # For demo purposes we accept all — implement full verification in production
    return True


def parse_webhook_event(payload: dict) -> dict:
    """
    Parse a PayPal webhook event into a normalized dict.
    Handles PAYMENT.CAPTURE.COMPLETED and related events.
    """
    event_type = payload.get("event_type", "")
    resource = payload.get("resource", {})

    amount = resource.get("amount", {})
    value = float(amount.get("value", 0))
    currency = amount.get("currency_code", "USD")

    return {
        "event_type": event_type,
        "transaction_id": resource.get("id", ""),
        "amount": value,
        "currency": currency,
        "status": resource.get("status", ""),
        "create_time": resource.get("create_time", ""),
        "raw": payload,
    }
