"""
Demo Data Seeder for Budget Guardian
Populates SQLite database with realistic PayPal sandbox transactions,
sample policies, and triggers the AI agent loop.
"""

from datetime import datetime, timedelta
import random
from backend.database import init_db, SessionLocal, TransactionDB, PolicyDB, AlertDB
from backend.agent.brain import run_agent_cycle


SAMPLE_MERCHANTS = [
    {"name": "GitHub Inc.", "category": "SaaS/Software", "typical_amount": 21.00},
    {"name": "Amazon Web Services", "category": "SaaS/Software", "typical_amount": 145.50},
    {"name": "DigitalOcean", "category": "SaaS/Software", "typical_amount": 48.00},
    {"name": "Uber Technologies", "category": "Travel", "typical_amount": 32.50},
    {"name": "DoorDash", "category": "Food & Dining", "typical_amount": 42.10},
    {"name": "Starbucks Coffee", "category": "Food & Dining", "typical_amount": 8.75},
    {"name": "Figma", "category": "SaaS/Software", "typical_amount": 15.00},
    {"name": "Spotify AB", "category": "Entertainment", "typical_amount": 10.99},
    {"name": "Apple Services", "category": "Entertainment", "typical_amount": 14.99},
    {"name": "OpenAI LLC", "category": "SaaS/Software", "typical_amount": 20.00},
]

SAMPLE_POLICIES = [
    "Alert me if I spend more than $300 on SaaS/Software in a week",
    "Flag any single transaction exceeding $500",
    "Warn me if my weekly total spending exceeds $1000",
]


def seed_demo_data():
    from backend.database import Base, engine
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()

    print("[SEED] Generating realistic PayPal sandbox transactions...")
    now = datetime.utcnow()

    # 1. Normal transactions over the past 25 days
    tx_count = 0
    for days_ago in range(25, 1, -1):
        num_today = random.randint(1, 3)
        for _ in range(num_today):
            merchant = random.choice(SAMPLE_MERCHANTS)
            amount = round(merchant["typical_amount"] * random.uniform(0.85, 1.15), 2)
            tx_date = now - timedelta(days=days_ago, hours=random.randint(1, 23), minutes=random.randint(1, 59))
            tx_id = f"PAYID-DEMO-{1000 + tx_count}"
            
            tx = TransactionDB(
                id=tx_id,
                transaction_id=tx_id,
                transaction_date=tx_date,
                transaction_amount=-amount,
                currency="USD",
                merchant_name=merchant["name"],
                category=merchant["category"],
                transaction_status="COMPLETED",
                transaction_note=f"Payment to {merchant['name']}",
                is_anomaly=False,
                is_evaluated=True,
            )
            db.add(tx)
            tx_count += 1

    # 2. Add realistic incoming payments (inflow)
    for days_ago in [20, 10]:
        tx_id = f"PAYID-INFLOW-{days_ago}"
        db.add(TransactionDB(
            id=tx_id,
            transaction_id=tx_id,
            transaction_date=now - timedelta(days=days_ago, hours=5),
            transaction_amount=1250.00,
            currency="USD",
            merchant_name="Acme Corp Client Payout",
            payer_name="Acme Corp",
            payer_email="finance@acmecorp.com",
            category="Transfer",
            transaction_status="COMPLETED",
            transaction_note="Invoice #1042 freelance settlement",
            is_anomaly=False,
            is_evaluated=True,
        ))

    # 3. Add ANOMALIES to demonstrate Budget Guardian's intelligence:
    # Anomaly 1: Massive unusual single transaction from a brand new merchant
    anom1_id = "PAYID-ANOMALY-881"
    db.add(TransactionDB(
        id=anom1_id,
        transaction_id=anom1_id,
        transaction_date=now - timedelta(hours=14),
        transaction_amount=-1489.00,
        currency="USD",
        merchant_name="Unknown Crypto Gateway Ltd",
        payer_name="Wallet Transfer",
        category="Transfer",
        transaction_status="COMPLETED",
        transaction_note="Offshore digital voucher purchase",
        is_anomaly=True,
        is_evaluated=True,
        anomaly_reason="Unusual high-value transaction ($1,489.00) from a merchant never seen in account history.",
    ))

    # Anomaly 2: Sudden 10x spike on recurring AWS bill
    anom2_id = "PAYID-ANOMALY-882"
    db.add(TransactionDB(
        id=anom2_id,
        transaction_id=anom2_id,
        transaction_date=now - timedelta(hours=4),
        transaction_amount=-890.00,
        currency="USD",
        merchant_name="Amazon Web Services",
        category="SaaS/Software",
        transaction_status="COMPLETED",
        transaction_note="AWS Cloud Services - Usage surge",
        is_anomaly=True,
        is_evaluated=True,
        anomaly_reason="Charge of $890.00 is 610% higher than historical AWS average ($145.50).",
    ))

    db.commit()

    # 4. Insert Policies
    print("[SEED] Adding natural language policies...")
    from backend.agent.policy_parser import parse_policy
    for policy_str in SAMPLE_POLICIES:
        structured = parse_policy(policy_str)
        import json
        p = PolicyDB(
            rule_text=policy_str,
            structured_rule=json.dumps(structured),
            is_active=True,
        )
        db.add(p)
    db.commit()

    # 5. Insert Alerts corresponding to the anomalies
    print("[SEED] Generating AI alerts...")
    db.add(AlertDB(
        transaction_id=anom1_id,
        severity="CRITICAL",
        message="Critical Outflow: $1,489.00 to Unknown Crypto Gateway Ltd",
        ai_explanation="This transaction exceeds your $500 single transaction threshold and is the first interaction with this merchant.",
        recommended_action="Review this charge immediately in your PayPal resolution center. If unauthorized, file a dispute.",
        is_read=False,
    ))

    db.add(AlertDB(
        transaction_id=anom2_id,
        severity="WARNING",
        message="AWS spend anomaly: $890.00 (historical average: $145.50)",
        ai_explanation="AWS bill spiked by over 600% compared to previous cycles, triggering your SaaS spending threshold.",
        recommended_action="Inspect active EC2 / RDS instances or check for unauthorized cloud API key usage.",
        is_read=False,
    ))

    db.commit()
    db.close()
    print("[SUCCESS] Seed complete! Launch FastAPI and Streamlit to view demo data.")


if __name__ == "__main__":
    seed_demo_data()
