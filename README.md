# 🛡️ Scope Creep Sentinel

**Protecting freelancers from silent scope expansion.**

Scope Creep Sentinel is an AI negotiation copilot for freelancers and small agencies, built for the **AWS Agents for Humans Hackathon**. It reads a project's Statement of Work (SOW), watches incoming client requests, and only interrupts the freelancer when there's a genuine scope decision to make — instead of letting "small" requests quietly turn into unpaid work.

🔗 **Live demo:** https://sc-8d5ba400a3eb4e528a5556d780e30bea.ecs.ap-south-1.on.aws/
📦 **Repository:** https://github.com/gayathri1703/scope-creep-sentinel

---

## 🧠 What it does

For every incoming client request, Scope Creep Sentinel:

1. Classifies it against the SOW as **IN_SCOPE**, **GRAY_AREA**, or **OUT_OF_SCOPE**
2. Estimates the additional effort and cost involved
3. Assesses cumulative scope-creep risk using the project's history
4. Decides whether the freelancer actually needs to intervene
5. If so, drafts three ready-to-send client responses and lets the human choose:

| Action | What it does |
|---|---|
| 💚 **Bill it** | Frame the request as a billable add-on |
| 🟠 **Negotiate it** | Open a conversation about scope/timeline trade-offs |
| ❤️ **Decline it** | Politely decline without sounding unhelpful |

## 🙋 Human-in-the-loop, by design

Scope Creep Sentinel never sends a message or commits to a decision on its own. It only classifies, estimates, and recommends — a human always makes the final call (Bill / Negotiate / Decline) before anything is logged as "sent." Requests that are clearly in scope and within limits are logged automatically without interrupting anyone; only genuine scope decisions reach the human.

## 🔄 Architecture & workflow

Three focused Strands agents, each with one responsibility:

| Agent | Responsibility |
|---|---|
| `ScopeAgent` | Classify a request against the SOW, estimate effort |
| `DecisionAgent` | Judge whether to interrupt the freelancer + risk level, using a ledger-lookup tool |
| `CommunicationAgent` | Draft the three client-facing messages |

## 🛠️ Tech stack

| Layer | Technology |
|---|---|
| Agent framework | [Strands Agents SDK](https://github.com/strands-agents) (Python) |
| LLM provider | Amazon Bedrock — Claude Sonnet 4.6 (`ap-south-1`) |
| Backend API | FastAPI + Uvicorn |
| Data models | Pydantic |
| Frontend | Vanilla HTML / CSS / JavaScript (served as static files by FastAPI, no build step) |
| Testing | pytest |
| AWS access | `boto3`, via existing AWS CLI credentials |

## 📁 Project structure
Scope-Creep-Sentinel/
├── main.py # CLI entry point (simulated client messages)
├── config.py # Shared bootstrap: MOCK_MODE, Bedrock model, paths
├── requirements.txt
├── README.md
├── .gitignore
├── agents/
│ ├── scope_agent.py # Real Strands agent: SOW-aware classification
│ ├── decision_agent.py # Real Strands agent + tool: risk/intervention judgment
│ ├── communication_agent.py # Real Strands agent: drafts client messages
│ └── mock_agents.py # Deterministic stand-ins used when MOCK_MODE=true
├── models/
│ └── scope_models.py # Pydantic domain models & structured-output schemas
├── services/
│ ├── scope_ledger.py # Persistence + arithmetic (no LLM calls)
│ └── project_state.py # Orchestrates the ledger + the three agents
├── api/
│ ├── schemas.py # API request/response models
│ └── server.py # FastAPI app — serves the dashboard + REST endpoints
├── web/
│ ├── index.html # Dashboard UI
│ ├── styles.css
│ └── app.js
├── data/
│ └── sample_sow.json # Example Statement of Work
└── tests/
├── test_scope_ledger.py
└── test_mock_mode.py


## ✅ Prerequisites

- Python 3.12+
- An AWS account with Amazon Bedrock access (only required if running with real agents — see `MOCK_MODE` below)
- AWS CLI configured (`aws configure` or `aws sso login`) with credentials that can call Bedrock in `ap-south-1`

## 🚀 How to run locally (Windows PowerShell)

```powershell
# 1. Clone the repository
git clone https://github.com/gayathri1703/scope-creep-sentinel.git
cd scope-creep-sentinel

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `MOCK_MODE` | `true` runs on deterministic mock agents with no Bedrock/AWS calls. `false` uses the real Strands/Bedrock pipeline. | `true` |

```powershell
# Run fully offline, no AWS calls:
$env:MOCK_MODE="true"

# Run against real Bedrock agents (requires valid AWS credentials):
$env:MOCK_MODE="false"
```

> ⚠️ **Never commit AWS keys, secrets, or `.env` files to GitHub.** This project reads credentials exclusively from your local AWS CLI configuration — nothing is hard-coded anywhere in the codebase, and nothing should be added.

### Start the application

```powershell
uvicorn api.server:app --reload --port 8000
```

Open your browser at:

http://127.0.0.1:8000/

The CLI is also available as a second, independent entry point onto the same backend:

```powershell
python main.py
```

## 🧪 Testing

```powershell
pytest tests/ -v
```

Covers the Scope Ledger's persistence/arithmetic logic and the full mock-mode workflow (classification → cost calculation → ledger updates) — no AWS access required to run the suite.

## 📄 License

No `LICENSE` file currently exists in this repository. Add one (e.g. MIT, Apache-2.0) at the repo root and reference it here before publishing the submission.