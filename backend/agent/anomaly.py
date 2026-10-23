"""
Anomaly Detection — uses statistical baselines + Gemini LLM reasoning
to identify unusual transactions.
"""

import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from backend.config import GEMINI_API_KEY

logger = logging.getLogger("budget_guardian.anomaly")

_model = None
if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        logger.warning(f"Could not initialize Gemini model in anomaly: {e}")

ANOMALY_PROMPT = """You are Budget Guardian's anomaly detection AI analyzing PayPal transactions.

You will receive:
1. A new transaction
2. Recent transaction history (last 30 days)
3. Statistical baselines per merchant

Evaluate if the transaction is anomalous. Consider:
- Unusual amount compared to typical spending at this merchant
- Unusual time of day or day of week
- New merchant not seen before
- Duplicate-looking transaction
- Suspiciously round numbers for large amounts

Respond with JSON only:
{
  "is_anomaly": true | false,
  "confidence": 0.0 to 1.0,
  "severity": "INFO" | "WARNING" | "CRITICAL",
  "reason": "<one sentence explanation>",
  "recommended_action": "<what the user should do>"
}
"""


def compute_merchant_baselines(transactions: List[Dict]) -> Dict[str, Dict]:
    """Compute mean and stdev of spending per merchant."""
    merchant_amounts: Dict[str, List[float]] = {}
    for t in transactions:
        m = t.get("merchant_name", "Unknown")
        amt = abs(t.get("transaction_amount", 0))
        if amt > 0:
            merchant_amounts.setdefault(m, []).append(amt)

    baselines = {}
    for merchant, amounts in merchant_amounts.items():
        baselines[merchant] = {
            "count": len(amounts),
            "mean": statistics.mean(amounts),
            "stdev": statistics.stdev(amounts) if len(amounts) > 1 else 0,
            "max": max(amounts),
        }
    return baselines


def statistical_anomaly_check(transaction: Dict, baselines: Dict) -> bool:
    """Quick statistical check before calling Gemini (saves API calls)."""
    merchant = transaction.get("merchant_name", "Unknown")
    amount = abs(transaction.get("transaction_amount", 0))

    if merchant not in baselines:
        return True  # New merchant — always flag

    b = baselines[merchant]
    if b["stdev"] > 0:
        z_score = (amount - b["mean"]) / b["stdev"]
        if abs(z_score) > 2.5:
            return True

    if amount > b["mean"] * 3:
        return True

    return False


def analyze_anomaly_with_ai(
    transaction: Dict,
    recent_transactions: List[Dict],
    baselines: Dict,
) -> Dict[str, Any]:
    """
    Use Gemini to provide a detailed anomaly assessment.
    Returns anomaly analysis dict.
    """
    merchant = transaction.get("merchant_name", "Unknown")
    amount = abs(transaction.get("transaction_amount", 0))
    baseline = baselines.get(merchant, {"count": 0, "mean": 0, "stdev": 0})

    if _model:
        recent_summary = []
        for t in recent_transactions[-10:]:
            recent_summary.append({
                "merchant": t.get("merchant_name"),
                "amount": t.get("transaction_amount"),
                "date": str(t.get("transaction_date", ""))[:10],
            })

        prompt = f"""{ANOMALY_PROMPT}

Transaction to analyze:
- Merchant: {merchant}
- Amount: ${amount:.2f} {transaction.get('currency', 'USD')}
- Date: {str(transaction.get('transaction_date', ''))[:19]}
- Note: {transaction.get('transaction_note', 'N/A')}

Historical baseline for this merchant:
- Past transactions: {baseline.get('count', 0)}
- Average amount: ${baseline.get('mean', 0):.2f}
- Std deviation: ${baseline.get('stdev', 0):.2f}
- Max ever: ${baseline.get('max', 0):.2f}

Recent transactions (last 10):
{json.dumps(recent_summary, indent=2)}
"""

        try:
            response = _model.generate_content(prompt)
            raw = response.text.strip()
            import re
            raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Gemini anomaly evaluation failed: {e}")

    # Fallback reasoning
    if merchant not in baselines or baseline.get("count", 0) == 0:
        return {
            "is_anomaly": True,
            "confidence": 0.85,
            "severity": "WARNING" if amount < 500 else "CRITICAL",
            "reason": f"First-time payment of ${amount:.2f} to new merchant '{merchant}'.",
            "recommended_action": "Verify if you authorized this new vendor in PayPal.",
        }
    else:
        multiplier = amount / baseline["mean"] if baseline["mean"] > 0 else 1
        return {
            "is_anomaly": True,
            "confidence": 0.80,
            "severity": "CRITICAL" if multiplier > 4 else "WARNING",
            "reason": f"Spend of ${amount:.2f} is {multiplier:.1f}x higher than typical ${baseline['mean']:.2f} average at {merchant}.",
            "recommended_action": "Review charge details or check for duplicate billing.",
        }


KNOWN_CATEGORIES = {
    "github": "SaaS/Software",
    "aws": "SaaS/Software",
    "amazon web services": "SaaS/Software",
    "digitalocean": "SaaS/Software",
    "figma": "SaaS/Software",
    "openai": "SaaS/Software",
    "slack": "SaaS/Software",
    "uber": "Travel",
    "lyft": "Travel",
    "airbnb": "Travel",
    "doordash": "Food & Dining",
    "starbucks": "Food & Dining",
    "mcdonald": "Food & Dining",
    "spotify": "Entertainment",
    "apple": "Entertainment",
    "netflix": "Entertainment",
}


def categorize_transaction(transaction: Dict) -> str:
    """Use Gemini or keyword heuristic to assign a spending category."""
    merchant = (transaction.get("merchant_name") or "").lower()
    note = (transaction.get("transaction_note") or "").lower()
    amount = transaction.get("transaction_amount", 0)

    # Heuristic match first (fastest)
    for kw, cat in KNOWN_CATEGORIES.items():
        if kw in merchant or kw in note:
            return cat

    if _model:
        prompt = f"""Categorize this PayPal transaction into exactly ONE category.
Categories: Food & Dining, Shopping, SaaS/Software, Transfer, Entertainment, Travel, Utilities, Healthcare, Education, Other

Merchant: {merchant}
Note: {note}
Amount: ${amount}

Reply with ONLY the category name, nothing else."""

        try:
            response = _model.generate_content(prompt)
            cat = response.text.strip().strip('"').strip("'")
            if cat in ["Food & Dining", "Shopping", "SaaS/Software", "Transfer", "Entertainment", "Travel", "Utilities", "Healthcare", "Education", "Other"]:
                return cat
        except Exception:
            pass

    return "Other"
