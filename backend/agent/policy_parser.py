"""
Policy Parser — converts natural language spending rules into structured JSON policies
using Google Gemini with a deterministic heuristic fallback.

Example input:  "Alert me if I spend more than $200 at any single merchant in a week"
Example output: {
    "type": "merchant_spend_limit",
    "threshold": 200,
    "window_days": 7,
    "action": "alert",
    "severity": "WARNING"
}
"""

import json
import re
import logging
from typing import Optional
from backend.config import GEMINI_API_KEY

logger = logging.getLogger("budget_guardian.policy_parser")

_model = None
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.warning(f"Could not initialize Gemini model: {e}")

POLICY_SYSTEM_PROMPT = """You are a financial rule parser for Budget Guardian, a PayPal spending monitor.

Convert the user's natural language spending rule into a structured JSON policy object.

Supported rule types:
- "merchant_spend_limit": alerts/blocks when spending at a single merchant exceeds threshold in a time window
- "category_spend_limit": alerts when a category (Food, SaaS, Transfer, etc.) exceeds threshold
- "single_transaction_limit": alerts/blocks any single transaction above threshold
- "daily_spend_limit": total daily spend limit
- "weekly_spend_limit": total weekly spend limit
- "monthly_spend_limit": total monthly spend limit
- "unusual_merchant": alert on transactions from new/unusual merchants

Return ONLY valid JSON with these fields:
{
  "type": "<rule_type>",
  "description": "<short human-readable description>",
  "threshold": <number or null>,
  "currency": "USD",
  "window_days": <number or null>,
  "merchant_name": "<specific merchant or null>",
  "category": "<category or null>",
  "action": "alert" | "hold" | "block",
  "severity": "INFO" | "WARNING" | "CRITICAL"
}

If the rule can't be parsed, return {"type": "unknown", "description": "Could not parse rule", "action": "alert", "severity": "INFO"}
"""


def _heuristic_parse_policy(rule_text: str) -> dict:
    """Fallback rule parser using pattern matching when Gemini API is unconfigured."""
    lower = rule_text.lower()
    
    # Extract dollar amount
    amount_match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:dollars|usd)", lower)
    threshold = float(amount_match.group(1) or amount_match.group(2)) if amount_match else None
    
    # Determine window
    window_days = None
    if "day" in lower or "daily" in lower:
        window_days = 1
    elif "week" in lower or "weekly" in lower:
        window_days = 7
    elif "month" in lower or "monthly" in lower:
        window_days = 30

    # Determine action
    action = "alert"
    severity = "WARNING"
    if "block" in lower or "reject" in lower:
        action = "block"
        severity = "CRITICAL"
    elif "hold" in lower or "pause" in lower:
        action = "hold"
        severity = "WARNING"

    # Category matching
    category = None
    for cat in ["saas", "software", "food", "dining", "travel", "entertainment", "transfer", "shopping"]:
        if cat in lower:
            category = "SaaS/Software" if cat in ("saas", "software") else ("Food & Dining" if cat in ("food", "dining") else cat.capitalize())
            break

    # Determine type
    if category:
        rtype = "category_spend_limit"
    elif "single" in lower or "transaction" in lower and not window_days:
        rtype = "single_transaction_limit"
    elif "week" in lower or "weekly" in lower:
        rtype = "weekly_spend_limit"
    elif "month" in lower or "monthly" in lower:
        rtype = "monthly_spend_limit"
    elif "day" in lower or "daily" in lower:
        rtype = "daily_spend_limit"
    elif "merchant" in lower:
        rtype = "merchant_spend_limit"
    else:
        rtype = "single_transaction_limit" if threshold else "unknown"

    return {
        "type": rtype,
        "description": rule_text.strip(),
        "threshold": threshold,
        "currency": "USD",
        "window_days": window_days or (7 if "limit" in rtype else None),
        "merchant_name": None,
        "category": category,
        "action": action,
        "severity": severity,
    }


def parse_policy(rule_text: str) -> dict:
    """Parse a natural language rule into a structured policy dict."""
    if _model:
        try:
            prompt = f"{POLICY_SYSTEM_PROMPT}\n\nRule: {rule_text}"
            response = _model.generate_content(prompt)
            raw = response.text.strip()
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Gemini policy parsing failed ({e}), using heuristic parser")

    return _heuristic_parse_policy(rule_text)


def evaluate_transaction_against_policies(
    transaction: dict,
    policies: list,
    recent_transactions: list,
) -> list:
    """
    Evaluate a transaction against all active policies.
    Returns list of triggered policy dicts with added 'trigger_reason'.
    """
    triggered = []
    for policy in policies:
        result = _check_policy(transaction, policy, recent_transactions)
        if result:
            triggered.append(result)
    return triggered


def _check_policy(transaction: dict, policy: dict, recent_txns: list) -> Optional[dict]:
    """Returns trigger info dict if policy is violated, else None."""
    rule = policy.get("structured_rule", {})
    if isinstance(rule, str):
        try:
            rule = json.loads(rule)
        except Exception:
            return None

    rtype = rule.get("type", "unknown")
    threshold = rule.get("threshold")
    window_days = rule.get("window_days", 7)
    amount = abs(transaction.get("transaction_amount", 0))
    merchant = transaction.get("merchant_name", "")
    category = transaction.get("category", "")

    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=window_days or 7)

    if rtype == "single_transaction_limit" and threshold:
        if amount > threshold:
            return _make_trigger(policy, transaction, f"Single transaction of ${amount:.2f} exceeds limit of ${threshold:.2f}")

    elif rtype == "merchant_spend_limit" and threshold:
        target_merchant = rule.get("merchant_name") or merchant
        window_total = sum(
            abs(t.get("transaction_amount", 0))
            for t in recent_txns
            if t.get("merchant_name") == target_merchant
            and t.get("transaction_date", datetime.utcnow()) >= cutoff
        )
        window_total += amount
        if window_total > threshold:
            return _make_trigger(policy, transaction,
                f"Spend at '{target_merchant}' reached ${window_total:.2f} (limit: ${threshold:.2f})")

    elif rtype == "weekly_spend_limit" and threshold:
        week_cutoff = datetime.utcnow() - timedelta(days=7)
        week_total = sum(
            abs(t.get("transaction_amount", 0))
            for t in recent_txns
            if t.get("transaction_amount", 0) < 0
            and t.get("transaction_date", datetime.utcnow()) >= week_cutoff
        )
        week_total += amount
        if week_total > threshold:
            return _make_trigger(policy, transaction,
                f"Weekly spend reached ${week_total:.2f} (limit: ${threshold:.2f})")

    elif rtype == "monthly_spend_limit" and threshold:
        month_cutoff = datetime.utcnow() - timedelta(days=30)
        month_total = sum(
            abs(t.get("transaction_amount", 0))
            for t in recent_txns
            if t.get("transaction_amount", 0) < 0
            and t.get("transaction_date", datetime.utcnow()) >= month_cutoff
        )
        month_total += amount
        if month_total > threshold:
            return _make_trigger(policy, transaction,
                f"Monthly spend reached ${month_total:.2f} (limit: ${threshold:.2f})")

    elif rtype == "category_spend_limit" and threshold and category:
        target_cat = (rule.get("category") or "").lower()
        if category.lower() == target_cat or target_cat in category.lower():
            cat_total = sum(
                abs(t.get("transaction_amount", 0))
                for t in recent_txns
                if target_cat in (t.get("category") or "").lower()
                and t.get("transaction_date", datetime.utcnow()) >= cutoff
            )
            cat_total += amount
            if cat_total > threshold:
                return _make_trigger(policy, transaction,
                    f"Category '{category}' spend reached ${cat_total:.2f} (limit: ${threshold:.2f})")

    return None


def _make_trigger(policy: dict, transaction: dict, reason: str) -> dict:
    rule = policy.get("structured_rule", {})
    if isinstance(rule, str):
        try:
            rule = json.loads(rule)
        except Exception:
            rule = {}
    return {
        "policy_id": policy.get("id"),
        "policy_description": rule.get("description", ""),
        "action": rule.get("action", "alert"),
        "severity": rule.get("severity", "WARNING"),
        "trigger_reason": reason,
        "transaction_id": transaction.get("transaction_id"),
    }
