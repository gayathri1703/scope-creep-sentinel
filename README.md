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