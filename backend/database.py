from sqlalchemy import create_engine, Column, String, Float, DateTime, Boolean, Text, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from backend.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TransactionDB(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    transaction_id = Column(String, unique=True, index=True)
    transaction_date = Column(DateTime)
    transaction_amount = Column(Float)
    currency = Column(String, default="USD")
    payer_name = Column(String, nullable=True)
    payer_email = Column(String, nullable=True)
    transaction_status = Column(String)
    transaction_note = Column(Text, nullable=True)
    merchant_name = Column(String, nullable=True)
    category = Column(String, nullable=True)           # AI-assigned
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(Text, nullable=True)
    is_evaluated = Column(Boolean, default=False)
    raw_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PolicyDB(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_text = Column(Text)                           # Original natural language
    structured_rule = Column(Text)                     # JSON string of parsed rule
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertDB(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, nullable=True)
    policy_id = Column(Integer, nullable=True)
    severity = Column(String, default="INFO")          # INFO | WARNING | CRITICAL
    message = Column(Text)
    ai_explanation = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
