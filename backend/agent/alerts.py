"""
Alert Generator — produces human-readable, actionable alerts with AI explanations.
"""

import json
import logging
from backend.config import GEMINI_API_KEY

logger = logging.getLogger("budget_guardian.alerts")

_model = None
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.warning(f"Could not initialize Gemini model in alerts: {e}")


def generate_alert_message(
    transaction: dict,
    trigger_reason: str,
    severity: str,
    policy_description: str = "",
) -> dict:
    """
    Generate a rich alert with AI explanation and recommendation.
    Returns dict with 'message', 'ai_explanation', 'recommended_action'.
    """
    merchant = transaction.get("merchant_name", "Unknown")
    amount = abs(transaction.get("transaction_amount", 0))
    currency = transaction.get("currency", "USD")
    tx_id = transaction.get("transaction_id", "N/A")

    if _model:
        prompt = f"""You are Budget Guardian, a smart PayPal spending watchdog.
A spending alert has been triggered. Write a clear, friendly, helpful alert message.

Alert Details:
- Merchant: {merchant}
- Amount: {currency} ${amount:.2f}
- Transaction ID: {tx_id}
- Trigger: {trigger_reason}
- Policy: {policy_description}
- Severity: {severity}

Respond with JSON:
{{
  "message": "<one-line summary for notification>",
  "ai_explanation": "<2-3 sentences explaining why this was flagged and what it means>",
  "recommended_action": "<specific action the user should take>"
}}"""

        try:
            response = _model.generate_content(prompt)
            raw = response.text.strip()
            import re
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Gemini alert generation failed: {e}")

    # Fallback explanation
    return {
        "message": f"{severity.upper()}: ${amount:.2f} to {merchant} flagged by Budget Guardian",
        "ai_explanation": f"{trigger_reason}. This activity was flagged during continuous transaction monitoring.",
        "recommended_action": f"Review transaction {tx_id} in your PayPal account. If unauthorized, report immediately.",
    }


def generate_weekly_summary(transactions: list, alerts: list) -> str:
    """Generate an AI-written weekly spending summary."""
    total_out = sum(abs(t.get("transaction_amount", 0)) for t in transactions if t.get("transaction_amount", 0) < 0)
    total_in = sum(t.get("transaction_amount", 0) for t in transactions if t.get("transaction_amount", 0) > 0)
    alert_count = len(alerts)

    # Category breakdown
    categories: dict = {}
    for t in transactions:
        cat = t.get("category", "Other") or "Other"
        categories[cat] = categories.get(cat, 0) + abs(t.get("transaction_amount", 0))

    top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]

    if _model:
        prompt = f"""You are Budget Guardian. Write a friendly, insightful weekly financial summary.

Weekly Stats:
- Total spent: ${total_out:.2f}
- Total received: ${total_in:.2f}  
- Alerts triggered: {alert_count}
- Top spending categories: {json.dumps(dict(top_cats))}
- Number of transactions: {len(transactions)}

Write a 3-4 sentence summary with a key insight and one actionable tip. Be conversational and helpful."""

        try:
            response = _model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            pass

    return f"This week you spent ${total_out:.2f} and received ${total_in:.2f} across {len(transactions)} transactions with {alert_count} alerts flagged by Budget Guardian."
