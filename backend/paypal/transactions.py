import httpx
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
from backend.config import PAYPAL_BASE_URL
from backend.paypal.auth import get_headers


def fetch_transactions(days_back: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch transactions from PayPal Transactions API for the past `days_back` days.
    Returns a list of normalized transaction dicts.
    """
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days_back)

    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    url = f"{PAYPAL_BASE_URL}/v1/reporting/transactions"
    params = {
        "start_date": start_str,
        "end_date": end_str,
        "fields": "all",
        "page_size": 500,
        "page": 1,
    }

    transactions = []
    while True:
        response = httpx.get(url, headers=get_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        for item in data.get("transaction_details", []):
            tx = _normalize_transaction(item)
            if tx:
                transactions.append(tx)

        total_pages = data.get("total_pages", 1)
        current_page = data.get("page", 1)
        if current_page >= total_pages:
            break
        params["page"] = current_page + 1

    return transactions


def _normalize_transaction(raw: Dict) -> Dict[str, Any]:
    """Flatten a PayPal transaction_detail into a clean dict."""
    try:
        info = raw.get("transaction_info", {})
        payer = raw.get("payer_info", {})
        cart = raw.get("cart_info", {})

        amount_str = info.get("transaction_amount", {}).get("value", "0")
        amount = float(amount_str)

        # PayPal encodes debits as negative
        date_str = info.get("transaction_initiation_date", "")
        tx_date = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S") if date_str else datetime.utcnow()

        payer_name = payer.get("payer_name", {})
        full_name = f"{payer_name.get('given_name', '')} {payer_name.get('surname', '')}".strip()

        merchant_name = (
            raw.get("payee_info", {}).get("merchant_info", {}).get("business_name")
            or info.get("paypal_account_id")
            or "Unknown"
        )

        return {
            "transaction_id": info.get("transaction_id", ""),
            "transaction_date": tx_date,
            "transaction_amount": amount,
            "currency": info.get("transaction_amount", {}).get("currency_code", "USD"),
            "payer_name": full_name or None,
            "payer_email": payer.get("email_address"),
            "transaction_status": info.get("transaction_status", ""),
            "transaction_note": info.get("transaction_note"),
            "merchant_name": merchant_name,
            "raw_json": json.dumps(raw),
        }
    except Exception:
        return None


def get_transaction_summary() -> Dict[str, Any]:
    """Quick summary stats for the dashboard."""
    txns = fetch_transactions(days_back=30)
    total_out = sum(t["transaction_amount"] for t in txns if t["transaction_amount"] < 0)
    total_in = sum(t["transaction_amount"] for t in txns if t["transaction_amount"] > 0)
    return {
        "total_transactions": len(txns),
        "total_outflow": abs(total_out),
        "total_inflow": total_in,
        "transactions": txns,
    }
