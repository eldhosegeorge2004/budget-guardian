"""
Budget Guardian — FastAPI Backend
Main application entry point.
"""

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from backend.database import init_db, get_db, TransactionDB, PolicyDB, AlertDB
from backend.paypal.auth import get_access_token
from backend.paypal.transactions import fetch_transactions
from backend.paypal.actions import send_payout
from backend.paypal.webhooks import parse_webhook_event
from backend.agent.brain import run_agent_cycle, sync_transactions
from backend.agent.policy_parser import parse_policy

logger = logging.getLogger("budget_guardian")

# ──────────────────────────────────────────
# Scheduler setup
# ──────────────────────────────────────────
scheduler = BackgroundScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    logger.info("✅ Database initialized")

    # Run an initial sync on startup
    try:
        from backend.database import SessionLocal
        db = SessionLocal()
        sync_transactions(db, days_back=30)
        db.close()
    except Exception as e:
        logger.warning(f"Initial sync failed (check PayPal credentials): {e}")

    # Schedule agent to run every 10 minutes
    scheduler.add_job(run_agent_cycle, "interval", minutes=10, id="agent_cycle")
    scheduler.start()
    logger.info("🤖 Agent scheduler started (every 10 minutes)")

    yield

    # Shutdown
    scheduler.shutdown()


app = FastAPI(
    title="Budget Guardian API",
    description="AI-powered PayPal spending monitor and autonomous agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────

class PolicyCreate(BaseModel):
    rule_text: str


class PayoutRequest(BaseModel):
    recipient_email: str
    amount: float
    currency: str = "USD"
    note: str = "Budget Guardian automated payout"


class AlertMarkRead(BaseModel):
    alert_id: int


# ──────────────────────────────────────────
# Health & Auth
# ──────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "Budget Guardian", "timestamp": datetime.utcnow().isoformat()}


@app.get("/paypal/auth-check")
def paypal_auth_check():
    """Verify PayPal credentials are working."""
    try:
        token = get_access_token()
        return {"status": "connected", "token_preview": token[:20] + "..."}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"PayPal auth failed: {str(e)}")


# ──────────────────────────────────────────
# Transactions
# ──────────────────────────────────────────

@app.get("/transactions")
def get_transactions(
    limit: int = 50,
    offset: int = 0,
    anomaly_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(TransactionDB)
    if anomaly_only:
        query = query.filter(TransactionDB.is_anomaly == True)
    query = query.order_by(TransactionDB.transaction_date.desc())
    total = query.count()
    txns = query.offset(offset).limit(limit).all()
    return {
        "total": total,
        "transactions": [_serialize_tx(t) for t in txns],
    }


@app.post("/transactions/sync")
def trigger_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually trigger a PayPal transaction sync."""
    background_tasks.add_task(run_agent_cycle)
    return {"status": "sync started", "message": "Agent cycle triggered in background"}


@app.get("/transactions/summary")
def get_summary(db: Session = Depends(get_db)):
    """Dashboard summary stats."""
    from sqlalchemy import func
    total = db.query(TransactionDB).count()
    anomalies = db.query(TransactionDB).filter(TransactionDB.is_anomaly == True).count()
    unread_alerts = db.query(AlertDB).filter(AlertDB.is_read == False).count()

    total_out = db.query(func.sum(TransactionDB.transaction_amount)).filter(
        TransactionDB.transaction_amount < 0
    ).scalar() or 0

    total_in = db.query(func.sum(TransactionDB.transaction_amount)).filter(
        TransactionDB.transaction_amount > 0
    ).scalar() or 0

    # Category breakdown
    cats = db.query(
        TransactionDB.category,
        func.sum(TransactionDB.transaction_amount).label("total")
    ).filter(
        TransactionDB.transaction_amount < 0,
        TransactionDB.category.isnot(None)
    ).group_by(TransactionDB.category).all()

    return {
        "total_transactions": total,
        "anomaly_count": anomalies,
        "unread_alerts": unread_alerts,
        "total_outflow": abs(float(total_out)),
        "total_inflow": float(total_in),
        "category_breakdown": [{"category": c[0], "amount": abs(float(c[1]))} for c in cats],
    }


# ──────────────────────────────────────────
# Policies
# ──────────────────────────────────────────

@app.get("/policies")
def get_policies(db: Session = Depends(get_db)):
    policies = db.query(PolicyDB).order_by(PolicyDB.created_at.desc()).all()
    return [_serialize_policy(p) for p in policies]


@app.post("/policies")
def create_policy(body: PolicyCreate, db: Session = Depends(get_db)):
    """Create a new spending policy from natural language."""
    structured = parse_policy(body.rule_text)
    policy = PolicyDB(
        rule_text=body.rule_text,
        structured_rule=json.dumps(structured),
        is_active=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return {
        "id": policy.id,
        "rule_text": policy.rule_text,
        "structured_rule": structured,
        "is_active": policy.is_active,
        "created_at": policy.created_at.isoformat(),
    }


@app.delete("/policies/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    policy = db.query(PolicyDB).filter(PolicyDB.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    policy.is_active = False
    db.commit()
    return {"status": "deactivated", "policy_id": policy_id}


# ──────────────────────────────────────────
# Alerts
# ──────────────────────────────────────────

@app.get("/alerts")
def get_alerts(unread_only: bool = False, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(AlertDB)
    if unread_only:
        query = query.filter(AlertDB.is_read == False)
    alerts = query.order_by(AlertDB.created_at.desc()).limit(limit).all()
    return [_serialize_alert(a) for a in alerts]


@app.post("/alerts/{alert_id}/read")
def mark_alert_read(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(AlertDB).filter(AlertDB.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    return {"status": "marked as read"}


# ──────────────────────────────────────────
# Demo Sandbox & Simulation (for Hackathon Judges)
# ──────────────────────────────────────────

class SimulateTxRequest(BaseModel):
    merchant_name: str
    amount: float
    currency: str = "USD"
    note: Optional[str] = "Simulated PayPal transaction"
    category: Optional[str] = None


@app.post("/demo/seed")
def seed_demo(background_tasks: BackgroundTasks):
    """Populate database with realistic sandbox PayPal transactions & policies."""
    from backend.seed_demo_data import seed_demo_data
    seed_demo_data()
    return {"status": "success", "message": "Demo data populated successfully!"}


@app.post("/demo/simulate-transaction")
def simulate_transaction(body: SimulateTxRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Simulate receiving a PayPal transaction in real-time to trigger agent response."""
    import uuid
    tx_id = f"PAYID-SIM-{uuid.uuid4().hex[:8].upper()}"
    tx = TransactionDB(
        id=tx_id,
        transaction_id=tx_id,
        transaction_date=datetime.utcnow(),
        transaction_amount=-abs(body.amount),
        currency=body.currency,
        merchant_name=body.merchant_name,
        transaction_status="COMPLETED",
        transaction_note=body.note,
        category=body.category,
    )
    db.add(tx)
    db.commit()
    background_tasks.add_task(run_agent_cycle)
    return {"status": "simulated", "transaction_id": tx_id, "amount": body.amount, "merchant": body.merchant_name}


# ──────────────────────────────────────────
# Payouts (autonomous action)
# ──────────────────────────────────────────

@app.post("/payouts/send")
def trigger_payout(body: PayoutRequest):
    """Send a PayPal payout to a recipient."""
    try:
        result = send_payout(
            recipient_email=body.recipient_email,
            amount=body.amount,
            currency=body.currency,
            note=body.note,
        )
        return {"status": "payout_sent", "paypal_response": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Payout failed: {str(e)}")


# ──────────────────────────────────────────
# Webhooks
# ──────────────────────────────────────────

@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive PayPal webhook events and process them."""
    body = await request.json()
    event = parse_webhook_event(body)
    # Trigger agent to process immediately
    background_tasks.add_task(run_agent_cycle)
    return {"status": "received", "event_type": event.get("event_type")}


# ──────────────────────────────────────────
# Serializers
# ──────────────────────────────────────────

def _serialize_tx(t: TransactionDB) -> dict:
    return {
        "id": t.id,
        "transaction_id": t.transaction_id,
        "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
        "transaction_amount": t.transaction_amount,
        "currency": t.currency,
        "payer_name": t.payer_name,
        "payer_email": t.payer_email,
        "transaction_status": t.transaction_status,
        "transaction_note": t.transaction_note,
        "merchant_name": t.merchant_name,
        "category": t.category,
        "is_anomaly": t.is_anomaly,
        "anomaly_reason": t.anomaly_reason,
    }


def _serialize_policy(p: PolicyDB) -> dict:
    rule = {}
    if p.structured_rule:
        try:
            rule = json.loads(p.structured_rule)
        except Exception:
            pass
    return {
        "id": p.id,
        "rule_text": p.rule_text,
        "structured_rule": rule,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }


def _serialize_alert(a: AlertDB) -> dict:
    return {
        "id": a.id,
        "transaction_id": a.transaction_id,
        "policy_id": a.policy_id,
        "severity": a.severity,
        "message": a.message,
        "ai_explanation": a.ai_explanation,
        "recommended_action": a.recommended_action,
        "is_read": a.is_read,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
