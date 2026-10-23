"""
Budget Guardian — Streamlit Dashboard
A real-time AI-powered PayPal spending monitor.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ──────────────────────────────────────────
# Config
# ──────────────────────────────────────────
API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Budget Guardian 🛡️",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 20px;
        color: white;
    }
    .alert-critical { border-left: 4px solid #ff4444; background: #2d1b1b; padding: 12px; border-radius: 6px; margin: 6px 0; }
    .alert-warning  { border-left: 4px solid #ffaa00; background: #2d2514; padding: 12px; border-radius: 6px; margin: 6px 0; }
    .alert-info     { border-left: 4px solid #4488ff; background: #1b2040; padding: 12px; border-radius: 6px; margin: 6px 0; }
    .anomaly-badge  { background: #ff4444; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; }
    .stButton button { width: 100%; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────
# API Helpers
# ──────────────────────────────────────────

def api_get(path: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, data: dict = None):
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_delete(path: str):
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ──────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────

with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/PayPal_logo.svg/320px-PayPal_logo.svg.png", width=120)
    st.title("🛡️ Budget Guardian")
    st.caption("AI-Powered PayPal Spending Monitor")
    st.divider()

    page = st.radio("Navigate", [
        "📊 Dashboard",
        "💳 Transactions",
        "🚨 Alerts",
        "📋 Policies",
        "💸 Send Payout",
        "🎮 Sandbox Simulator",
        "⚙️ Settings",
    ])

    st.divider()

    # Live connection status
    health = api_get("/health")
    if health:
        st.success("✅ Backend Connected")
    else:
        st.error("❌ Backend Offline")
        st.caption("Run: `uvicorn backend.main:app --reload`")

    # PayPal status
    paypal = api_get("/paypal/auth-check")
    if paypal and paypal.get("status") == "connected":
        st.success("✅ PayPal Connected")
    else:
        st.info("ℹ️ PayPal Sandbox (Demo mode)")

    st.divider()
    if st.button("🔄 Sync PayPal Now"):
        result = api_post("/transactions/sync")
        if result:
            st.success("Sync triggered! Refresh in ~10s")

    if st.button("🌱 Load Demo Sandbox Data"):
        result = api_post("/demo/seed")
        if result:
            st.success("Demo dataset loaded!")
            st.rerun()


# ──────────────────────────────────────────
# Page: Dashboard
# ──────────────────────────────────────────

if page == "📊 Dashboard":
    st.title("📊 Dashboard")

    summary = api_get("/transactions/summary")
    alerts = api_get("/alerts", {"unread_only": True, "limit": 5})

    if summary:
        # KPI Row
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("💰 Total Transactions", summary.get("total_transactions", 0))
        col2.metric("📤 Total Outflow", f"${summary.get('total_outflow', 0):,.2f}")
        col3.metric("📥 Total Inflow", f"${summary.get('total_inflow', 0):,.2f}")
        col4.metric("🔴 Anomalies Detected", summary.get("anomaly_count", 0))
        col5.metric("🔔 Unread Alerts", summary.get("unread_alerts", 0))

        st.divider()

        col_left, col_right = st.columns([1.5, 1])

        # Category donut chart
        with col_left:
            cats = summary.get("category_breakdown", [])
            if cats:
                df_cats = pd.DataFrame(cats)
                fig = px.pie(
                    df_cats, names="category", values="amount",
                    title="💳 Spending by Category",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig.update_traces(textposition="inside", textinfo="percent+label")
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="white",
                    showlegend=True,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No categorized transactions yet. Sync to get started.")

        # Recent unread alerts
        with col_right:
            st.subheader("🚨 Recent Alerts")
            if alerts:
                for alert in alerts:
                    sev = alert.get("severity", "INFO")
                    css_class = f"alert-{sev.lower()}"
                    icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(sev, "⚪")
                    st.markdown(f"""
                    <div class="{css_class}">
                        <b>{icon} {sev}</b><br>
                        {alert.get('message', '')}<br>
                        <small>💡 {alert.get('recommended_action', '')}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ No unread alerts — all clear!")

    # Recent Transactions Table
    st.divider()
    st.subheader("📜 Recent Transactions")
    txns = api_get("/transactions", {"limit": 10})
    if txns and txns.get("transactions"):
        df = pd.DataFrame(txns["transactions"])
        df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.strftime("%Y-%m-%d %H:%M")
        df["amount_display"] = df["transaction_amount"].apply(
            lambda x: f"{'🔴 -' if x < 0 else '🟢 +'}\${abs(x):.2f}"
        )
        df["anomaly"] = df["is_anomaly"].apply(lambda x: "⚠️ ANOMALY" if x else "✅")
        display_cols = ["transaction_date", "merchant_name", "amount_display", "category", "anomaly", "transaction_status"]
        st.dataframe(df[display_cols].rename(columns={
            "transaction_date": "Date",
            "merchant_name": "Merchant",
            "amount_display": "Amount",
            "category": "Category",
            "anomaly": "Status",
            "transaction_status": "PayPal Status",
        }), use_container_width=True, hide_index=True)


# ──────────────────────────────────────────
# Page: Transactions
# ──────────────────────────────────────────

elif page == "💳 Transactions":
    st.title("💳 Transactions")

    col1, col2 = st.columns([3, 1])
    with col2:
        anomaly_only = st.checkbox("🔴 Anomalies only")

    txns_data = api_get("/transactions", {"limit": 200, "anomaly_only": anomaly_only})

    if txns_data and txns_data.get("transactions"):
        txns = txns_data["transactions"]
        df = pd.DataFrame(txns)
        df["transaction_date"] = pd.to_datetime(df["transaction_date"])
        df = df.sort_values("transaction_date", ascending=False)

        # Timeline chart
        df_chart = df[df["transaction_amount"] < 0].copy()
        df_chart["abs_amount"] = df_chart["transaction_amount"].abs()
        if not df_chart.empty:
            fig = px.bar(
                df_chart.head(50), x="transaction_date", y="abs_amount",
                color="category", title="💸 Spending Over Time",
                labels={"abs_amount": "Amount (USD)", "transaction_date": "Date"},
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="white")
            st.plotly_chart(fig, use_container_width=True)

        # Full table
        df["amount_fmt"] = df["transaction_amount"].apply(lambda x: f"{'- ' if x < 0 else '+ '}\${abs(x):.2f}")
        df["anomaly_flag"] = df["is_anomaly"].apply(lambda x: "⚠️" if x else "")
        display = df[["transaction_date", "merchant_name", "amount_fmt", "currency", "category",
                       "anomaly_flag", "transaction_status", "payer_email"]].rename(columns={
            "transaction_date": "Date", "merchant_name": "Merchant", "amount_fmt": "Amount",
            "currency": "Currency", "category": "Category", "anomaly_flag": "Flag",
            "transaction_status": "Status", "payer_email": "Email",
        })
        st.dataframe(display, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(txns)} of {txns_data.get('total', 0)} transactions")
    else:
        st.info("No transactions found. Click **Sync Now** in the sidebar.")


# ──────────────────────────────────────────
# Page: Alerts
# ──────────────────────────────────────────

elif page == "🚨 Alerts":
    st.title("🚨 Alerts")

    col1, col2 = st.columns([3, 1])
    with col2:
        unread_only = st.checkbox("Unread only", value=False)

    alerts = api_get("/alerts", {"unread_only": unread_only, "limit": 100})

    if alerts:
        for alert in alerts:
            sev = alert.get("severity", "INFO")
            css_class = f"alert-{sev.lower()}"
            icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(sev, "⚪")
            read_status = "" if alert.get("is_read") else "🆕 "
            ts = alert.get("created_at", "")[:16]

            with st.expander(f"{read_status}{icon} {sev} — {alert.get('message', '')[:80]} ({ts})"):
                st.markdown(f"**📋 Full Message:** {alert.get('message', '')}")
                st.markdown(f"**🤖 AI Explanation:** {alert.get('ai_explanation', '')}")
                st.markdown(f"**💡 Recommended Action:** {alert.get('recommended_action', '')}")
                st.caption(f"Transaction ID: {alert.get('transaction_id', 'N/A')} | Alert ID: {alert.get('id')}")
                if not alert.get("is_read"):
                    if st.button("✅ Mark as Read", key=f"read_{alert['id']}"):
                        api_post(f"/alerts/{alert['id']}/read")
                        st.rerun()
    else:
        st.success("🎉 No alerts — your spending looks healthy!")


# ──────────────────────────────────────────
# Page: Policies
# ──────────────────────────────────────────

elif page == "📋 Policies":
    st.title("📋 Spending Policies")
    st.caption("Define spending rules in plain English. Budget Guardian's AI will parse and enforce them automatically.")

    # Add new policy
    with st.form("new_policy_form"):
        st.subheader("➕ Add New Policy")
        example = st.selectbox("Quick examples (or type your own below):", [
            "Type your own...",
            "Alert me if I spend more than $500 at any single merchant in a week",
            "Block any single transaction over $1000",
            "Warn me if my monthly total spending exceeds $3000",
            "Flag any transaction from a merchant I've never used before",
            "Alert if I spend more than $200 on SaaS/Software in a month",
        ])
        rule_text = st.text_area(
            "Your rule (natural language):",
            value="" if example == "Type your own..." else example,
            height=80,
        )
        submitted = st.form_submit_button("🤖 Parse & Add Policy")
        if submitted and rule_text:
            with st.spinner("Asking Gemini to parse your rule..."):
                result = api_post("/policies", {"rule_text": rule_text})
            if result:
                st.success("✅ Policy created!")
                st.json(result.get("structured_rule", {}))
                st.rerun()

    st.divider()
    st.subheader("📋 Active Policies")

    policies = api_get("/policies")
    if policies:
        for p in policies:
            if not p.get("is_active"):
                continue
            rule = p.get("structured_rule", {})
            sev = rule.get("severity", "INFO")
            icon = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(sev, "⚪")

            col1, col2 = st.columns([5, 1])
            with col1:
                with st.expander(f"{icon} {p.get('rule_text', '')[:100]}"):
                    st.markdown(f"**Type:** `{rule.get('type', 'unknown')}`")
                    st.markdown(f"**Description:** {rule.get('description', '')}")
                    if rule.get("threshold"):
                        st.markdown(f"**Threshold:** \${rule.get('threshold'):.2f} {rule.get('currency', 'USD')}")
                    if rule.get("window_days"):
                        st.markdown(f"**Time Window:** {rule.get('window_days')} days")
                    st.markdown(f"**Action:** `{rule.get('action', 'alert')}` | **Severity:** `{sev}`")
                    st.caption(f"Created: {p.get('created_at', '')[:10]} | ID: {p.get('id')}")
            with col2:
                if st.button("🗑️ Remove", key=f"del_{p['id']}"):
                    api_delete(f"/policies/{p['id']}")
                    st.rerun()
    else:
        st.info("No policies yet. Add your first rule above!")


# ──────────────────────────────────────────
# Page: Send Payout
# ──────────────────────────────────────────

elif page == "💸 Send Payout":
    st.title("💸 Send PayPal Payout")
    st.caption("Trigger autonomous payouts via the PayPal Payouts API (sandbox)")

    with st.form("payout_form"):
        recipient = st.text_input("Recipient Email", placeholder="sb-recipient@example.com")
        amount = st.number_input("Amount (USD)", min_value=0.01, value=10.00, step=0.01)
        note = st.text_area("Note", value="Budget Guardian automated payout", height=60)
        submitted = st.form_submit_button("💸 Send Payout via PayPal")
        if submitted and recipient:
            with st.spinner("Sending payout..."):
                result = api_post("/payouts/send", {
                    "recipient_email": recipient,
                    "amount": amount,
                    "note": note,
                })
            if result:
                st.success("✅ Payout sent!")
                st.json(result)


# ──────────────────────────────────────────
# Page: Sandbox Simulator (Demo & Testing)
# ──────────────────────────────────────────

elif page == "🎮 Sandbox Simulator":
    st.title("🎮 PayPal Sandbox Simulator")
    st.caption("Inject simulated PayPal transactions in real time to test how the AI agent detects anomalies and evaluates policies.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("⚡ Quick Scenarios")
        st.write("Click any scenario to simulate a transaction:")
        
        if st.button("🚨 Simulate Large Anomaly ($1,490 to Crypto Merchant)"):
            with st.spinner("Simulating PayPal charge..."):
                res = api_post("/demo/simulate-transaction", {
                    "merchant_name": "Offshore Crypto Exchange",
                    "amount": 1490.00,
                    "note": "Immediate digital asset withdrawal",
                    "category": "Transfer",
                })
                if res:
                    st.success("Transaction simulated! Checking agent evaluation...")
                    st.info("Navigate to 🚨 Alerts or 📊 Dashboard to see Budget Guardian's live detection.")

        if st.button("⚠️ Simulate SaaS Spike ($650 AWS Charge)"):
            with st.spinner("Simulating PayPal charge..."):
                res = api_post("/demo/simulate-transaction", {
                    "merchant_name": "Amazon Web Services",
                    "amount": 650.00,
                    "note": "AWS Elastic Compute Surge",
                    "category": "SaaS/Software",
                })
                if res:
                    st.success("Transaction simulated! Anomaly detection triggered.")

        if st.button("☕ Simulate Normal Expense ($14.50 Coffee)"):
            with st.spinner("Simulating PayPal charge..."):
                res = api_post("/demo/simulate-transaction", {
                    "merchant_name": "Starbucks Coffee",
                    "amount": 14.50,
                    "note": "Morning team breakfast",
                    "category": "Food & Dining",
                })
                if res:
                    st.success("Normal transaction logged without alert.")

    with col2:
        st.subheader("🛠️ Custom Transaction")
        with st.form("custom_sim_form"):
            custom_merchant = st.text_input("Merchant Name", "Custom Vendor LLC")
            custom_amount = st.number_input("Amount ($ USD)", min_value=1.0, value=750.0, step=10.0)
            custom_category = st.selectbox("Category", ["SaaS/Software", "Food & Dining", "Travel", "Entertainment", "Transfer", "Other"])
            custom_note = st.text_input("Note", "Custom test charge")
            
            sim_submit = st.form_submit_button("🚀 Fire Simulated PayPal Event")
            if sim_submit:
                with st.spinner("Firing event..."):
                    res = api_post("/demo/simulate-transaction", {
                        "merchant_name": custom_merchant,
                        "amount": custom_amount,
                        "note": custom_note,
                        "category": custom_category,
                    })
                    if res:
                        st.success(f"Simulated ${custom_amount:.2f} payment to {custom_merchant}!")
                        st.balloons()


# ──────────────────────────────────────────
# Page: Settings
# ──────────────────────────────────────────

elif page == "⚙️ Settings":
    st.title("⚙️ Settings")

    st.subheader("🔗 API Status")
    health = api_get("/health")
    paypal = api_get("/paypal/auth-check")

    if health:
        st.success(f"✅ Backend API: {health.get('status')} — {health.get('timestamp')}")
    else:
        st.error("❌ Backend API is offline")

    if paypal and paypal.get("status") == "connected":
        st.success("✅ PayPal Sandbox: Connected")
    else:
        st.error("❌ PayPal: Check your CLIENT_ID and CLIENT_SECRET in .env")

    st.divider()
    st.subheader("📖 Configuration")
    st.markdown("""
    Configure your credentials in the `.env` file:
    ```
    PAYPAL_CLIENT_ID=your_sandbox_client_id
    PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
    PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
    GEMINI_API_KEY=your_gemini_api_key
    ```
    
    **Get your credentials:**
    - [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/)
    - [Google AI Studio (Gemini)](https://aistudio.google.com/app/apikey)
    """)

    st.divider()
    st.subheader("🤖 Agent Schedule")
    st.info("The AI agent runs every **10 minutes** automatically. Use **Sync Now** for an immediate refresh.")
