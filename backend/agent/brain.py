"""
Budget Guardian AI Agent — the core autonomous loop.

Responsibilities:
1. Periodically sync PayPal transactions
2. Categorize new transactions with AI
3. Run anomaly detection
4. Evaluate all active policies
5. Generate and store alerts
"""

import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.database import SessionLocal, TransactionDB, PolicyDB, AlertDB
from backend.paypal.auth import is_paypal_configured
from backend.paypal.transactions import fetch_transactions
from backend.agent.anomaly import (
    compute_merchant_baselines,
    statistical_anomaly_check,
    analyze_anomaly_with_ai,
    categorize_transaction,
)
from backend.agent.policy_parser import evaluate_transaction_against_policies
from backend.agent.alerts import generate_alert_message

logger = logging.getLogger("budget_guardian.agent")
logging.basicConfig(level=logging.INFO)


def sync_transactions(db: Session, days_back: int = 30) -> int:
    """Fetch PayPal transactions and store new ones in DB. Returns count of new txns."""
    if not is_paypal_configured():
        logger.info("ℹ️ PayPal API credentials not set — using local demo transaction store.")
        return 0

    try:
        transactions = fetch_transactions(days_back=days_back)
    except Exception as e:
        logger.warning(f"Could not reach PayPal sandbox API: {e}")
        return 0

    new_count = 0
    for tx in transactions:
        existing = db.query(TransactionDB).filter_by(
            transaction_id=tx["transaction_id"]
        ).first()
        if not existing:
            record = TransactionDB(
                id=tx["transaction_id"],
                **{k: v for k, v in tx.items() if k != "id"},
            )
            db.add(record)
            new_count += 1

    db.commit()
    logger.info(f"Synced {new_count} new transactions from PayPal")
    return new_count


def run_agent_cycle():
    """Main agent loop — called by scheduler every N minutes or on event trigger."""
    db = SessionLocal()
    try:
        logger.info("🤖 Agent cycle started")

        # 1. Sync transactions from PayPal if configured
        try:
            sync_transactions(db, days_back=30)
        except Exception as e:
            logger.info(f"PayPal sync skipped or offline: {e}")

        # 2. Load all unevaluated transactions
        unevaluated = db.query(TransactionDB).filter(
            TransactionDB.is_evaluated == False
        ).all()

        if not unevaluated:
            logger.info("No unevaluated transactions. Agent cycle done.")
            return

        # 3. Load all transactions for baselines
        all_txns = db.query(TransactionDB).order_by(
            TransactionDB.transaction_date.asc()
        ).all()
        all_txns_dicts = [_tx_to_dict(t) for t in all_txns]

        baselines = compute_merchant_baselines(all_txns_dicts)

        # 4. Load active policies
        policies = db.query(PolicyDB).filter_by(is_active=True).all()
        policies_dicts = [_policy_to_dict(p) for p in policies]

        # 5. Process each unevaluated transaction
        for tx in unevaluated:
            tx_dict = _tx_to_dict(tx)

            # Categorize if not already categorized
            if not tx.category:
                category = categorize_transaction(tx_dict)
                tx.category = category
                tx_dict["category"] = category

            # Anomaly detection
            if statistical_anomaly_check(tx_dict, baselines):
                anomaly_result = analyze_anomaly_with_ai(
                    tx_dict, all_txns_dicts, baselines
                )
                if anomaly_result.get("is_anomaly"):
                    tx.is_anomaly = True
                    tx.anomaly_reason = anomaly_result.get("reason", "")

                    # Create anomaly alert
                    alert_content = generate_alert_message(
                        tx_dict,
                        trigger_reason=anomaly_result.get("reason", "Anomaly detected"),
                        severity=anomaly_result.get("severity", "WARNING"),
                    )
                    alert = AlertDB(
                        transaction_id=tx.transaction_id,
                        severity=anomaly_result.get("severity", "WARNING"),
                        message=alert_content["message"],
                        ai_explanation=alert_content["ai_explanation"],
                        recommended_action=alert_content["recommended_action"],
                    )
                    db.add(alert)

            # Policy evaluation
            triggered_policies = evaluate_transaction_against_policies(
                tx_dict, policies_dicts, all_txns_dicts
            )
            for trigger in triggered_policies:
                alert_content = generate_alert_message(
                    tx_dict,
                    trigger_reason=trigger["trigger_reason"],
                    severity=trigger["severity"],
                    policy_description=trigger.get("policy_description", ""),
                )
                alert = AlertDB(
                    transaction_id=tx.transaction_id,
                    policy_id=trigger.get("policy_id"),
                    severity=trigger["severity"],
                    message=alert_content["message"],
                    ai_explanation=alert_content["ai_explanation"],
                    recommended_action=alert_content["recommended_action"],
                )
                db.add(alert)

            tx.is_evaluated = True

        db.commit()
        logger.info(f"✅ Agent cycle complete — processed {len(unevaluated)} transactions")

    except Exception as e:
        logger.error(f"Agent cycle error: {e}", exc_info=True)
    finally:
        db.close()


def _tx_to_dict(tx: TransactionDB) -> dict:
    return {
        "transaction_id": tx.transaction_id,
        "transaction_date": tx.transaction_date,
        "transaction_amount": tx.transaction_amount,
        "currency": tx.currency,
        "payer_name": tx.payer_name,
        "payer_email": tx.payer_email,
        "transaction_status": tx.transaction_status,
        "transaction_note": tx.transaction_note,
        "merchant_name": tx.merchant_name,
        "category": tx.category,
        "is_anomaly": tx.is_anomaly,
    }


def _policy_to_dict(policy: PolicyDB) -> dict:
    rule = {}
    if policy.structured_rule:
        try:
            rule = json.loads(policy.structured_rule)
        except Exception:
            pass
    return {
        "id": policy.id,
        "rule_text": policy.rule_text,
        "structured_rule": rule,
    }
