# 🛡️ Budget Guardian

> **PayPal AI Hackathon 2026 Submission**

An autonomous AI agent that monitors your PayPal spending, detects anomalies, enforces natural-language policies, and takes action — all powered by Google Gemini and the PayPal REST APIs.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![PayPal](https://img.shields.io/badge/PayPal-Sandbox-003087.svg)](https://developer.paypal.com)
[![Gemini](https://img.shields.io/badge/AI-Google%20Gemini-4285F4.svg)](https://aistudio.google.com)

---

## 🎯 What It Does

**Budget Guardian** is your always-on financial watchdog for PayPal:

| Feature | Description |
|---|---|
| 🔄 **Auto-Sync** | Pulls transactions from PayPal every 10 minutes |
| 🏷️ **AI Categorization** | Gemini auto-tags each transaction (Food, SaaS, Transfer, etc.) |
| 🔍 **Anomaly Detection** | Statistical + LLM analysis flags unusual spending patterns |
| 📋 **Natural Language Policies** | Write rules like "alert me if I spend over $500 at any merchant in a week" |
| 🚨 **Smart Alerts** | AI-generated explanations + actionable recommendations for every alert |
| 💸 **Autonomous Payouts** | Trigger PayPal payouts directly from the dashboard |
| 🔗 **Webhook Support** | Real-time event processing via PayPal Webhooks |

---

## 🏗️ Architecture

```
PayPal Sandbox → Webhooks/REST API → FastAPI Backend → SQLite DB
                                           ↓
                               AI Agent Loop (Gemini)
                               ├── Categorize transactions
                               ├── Detect anomalies
                               ├── Evaluate policies
                               └── Generate alerts
                                           ↓
                               Streamlit Dashboard (real-time UI)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [PayPal Developer account](https://developer.paypal.com) (free sandbox)
- [Google AI Studio API key](https://aistudio.google.com/app/apikey) (free)

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/budget-guardian.git
cd budget-guardian
pip install -r requirements.txt
```

### 2. Configure Credentials

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
PAYPAL_CLIENT_ID=your_sandbox_client_id
PAYPAL_CLIENT_SECRET=your_sandbox_client_secret
PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
GEMINI_API_KEY=your_gemini_api_key
```

**Getting PayPal sandbox credentials:**
1. Go to [developer.paypal.com](https://developer.paypal.com/dashboard/applications/sandbox)
2. Create a new app → select **Sandbox**
3. Copy `Client ID` and `Secret`

**Getting Gemini API key:**
1. Go to [aistudio.google.com](https://aistudio.google.com/app/apikey)
2. Create API key → copy it

### 3. Run the Backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 4. Run the Dashboard (separate terminal)

```bash
streamlit run frontend/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ☁️ Deploy to Render (Official Hackathon Sponsor)

Budget Guardian is configured for 1-click deployment on [Render](https://render.com) via Blueprint (`render.yaml`):

1. Push your repository to GitHub.
2. Go to your [Render Dashboard](https://dashboard.render.com/) and click **New +** $\rightarrow$ **Blueprint**.
3. Connect your GitHub repository. Render reads `render.yaml` and sets up:
   - `budget-guardian-api` (FastAPI backend service)
   - `budget-guardian-dashboard` (Streamlit frontend service)
4. Add your optional `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `GEMINI_API_KEY` in the Render environment variables tab.
5. Click **Apply** — Render automatically builds, seeds sample data, links the frontend to the backend, and provisions public HTTPS URLs!

*Alternatively, deploy as a single service using the command:*
```bash
python run_unified.py
```

---

## 📁 Project Structure

```
budget-guardian/
├── backend/
│   ├── main.py              # FastAPI app + REST endpoints
│   ├── database.py          # SQLAlchemy models + DB setup
│   ├── config.py            # Environment config
│   ├── paypal/
│   │   ├── auth.py          # PayPal OAuth2 token management
│   │   ├── transactions.py  # Transaction fetch + normalization
│   │   ├── actions.py       # Payout execution
│   │   └── webhooks.py      # Webhook event parsing
│   └── agent/
│       ├── brain.py         # Core autonomous agent loop
│       ├── policy_parser.py # NL rule → structured policy (Gemini)
│       ├── anomaly.py       # Anomaly detection (stats + Gemini)
│       └── alerts.py        # AI alert generation
├── frontend/
│   └── app.py              # Streamlit dashboard
├── requirements.txt
├── .env.example
├── LICENSE
└── README.md
```

---

## 🔌 PayPal APIs Used

| API | Usage |
|---|---|
| [`/v1/oauth2/token`](https://developer.paypal.com/api/rest/) | OAuth2 client credentials auth |
| [`/v1/reporting/transactions`](https://developer.paypal.com/docs/api/transaction-search/v1/) | Fetch transaction history |
| [`/v1/payments/payouts`](https://developer.paypal.com/docs/api/payments.payouts-batch/v1/) | Autonomous payout execution |
| [Webhooks](https://developer.paypal.com/docs/api/webhooks/v1/) | Real-time transaction events |

---

## 🤖 AI Integration

**Model:** Google Gemini 1.5 Flash

**AI is used for:**
1. **Transaction Categorization** — Every transaction is tagged with a spending category
2. **Natural Language Policy Parsing** — Plain English rules are converted to structured JSON policies
3. **Anomaly Explanation** — When a transaction is flagged, Gemini explains *why* it's unusual
4. **Alert Generation** — Each alert includes an AI-written explanation and recommendation
5. **Weekly Summaries** — AI-written spending digest with insights

---

## 🌐 API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/paypal/auth-check` | Verify PayPal connection |
| GET | `/transactions` | List transactions |
| POST | `/transactions/sync` | Manual sync trigger |
| GET | `/transactions/summary` | Dashboard stats |
| GET | `/policies` | List policies |
| POST | `/policies` | Create NL policy |
| DELETE | `/policies/{id}` | Remove policy |
| GET | `/alerts` | List alerts |
| POST | `/alerts/{id}/read` | Mark alert read |
| POST | `/payouts/send` | Send PayPal payout |
| POST | `/webhooks/paypal` | Receive PayPal events |

---

## 🎯 Example Policies (Natural Language)

```
"Alert me if I spend more than $500 at any single merchant in a week"
"Block any single transaction over $1000"
"Warn me if my monthly total spending exceeds $3000"
"Flag any transaction from a merchant I've never used before"
"Alert if I spend more than $200 on SaaS in a month"
```

---

## 📽️ Demo Video

> [Watch on YouTube](https://youtube.com/your-demo-link)

---

## 🏆 Built For

[PayPal AI Hackathon 2026](https://paypalaihackathon.devpost.com/) — *Build What's Next with PayPal and AI*

---

## 📄 License

MIT — see [LICENSE](LICENSE)
