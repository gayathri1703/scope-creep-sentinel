# Scope Creep Sentinel

**AI-powered scope management for freelancers, consultants, and small agencies.**

Scope Creep Sentinel watches client requests against a project's Statement of Work (SOW), detects potential scope creep, estimates the additional effort and cost, evaluates accumulated project risk, and gives the human decision-maker clear response options.

Instead of allowing "small" client requests to quietly become unpaid work, the system creates a structured decision point.

Built for the **AWS Agents for Humans Hackathon 2026 — Professional Agents track**.

---

## The Problem

Freelancers and small agencies often lose money through scope creep.

A request such as:

> "Can you also add a loyalty program?"

may look like a small change, but it can introduce significant additional development work.

The problem is not simply identifying whether a request is inside or outside the contract.

The real problem is answering:

- Is this request covered by the SOW?
- How much additional effort could it require?
- What is the financial impact?
- How much scope creep has already accumulated?
- Does the freelancer need to make a decision?
- What should they tell the client?

Scope Creep Sentinel turns those questions into one workflow.

---

# What Scope Creep Sentinel Does

The system:

1. Loads a structured Statement of Work.
2. Receives a client request.
3. Uses a **Strands Scope Agent** to classify the request:
   - `IN_SCOPE`
   - `GRAY_AREA`
   - `OUT_OF_SCOPE`
4. Estimates additional effort.
5. Calculates cost deterministically from the hourly rate.
6. Uses a **Strands Decision Agent** to evaluate risk using the project's accumulated scope history.
7. Generates three possible client responses:
   - Bill it
   - Negotiate it
   - Decline it
8. Lets the human make the final decision.
9. Persists the request and decision in the Scope Ledger.
10. Updates cumulative scope-creep and financial-risk metrics.

---

# Why This Is an Agent

This is not a chatbot that simply answers a question.

The system maintains project state and uses multiple specialized agents.

### 1. Intake Agent

Used for the real Gmail workflow.

Its job is to determine whether an incoming email is actually a client/project request.

Examples:

- Newsletter → ignore
- Marketing email → ignore
- Deployment notification → ignore
- "Can you add a mobile app?" → forward for scope analysis

The Intake Agent produces structured output rather than free-form text.

---

### 2. Scope Agent

The Scope Agent evaluates the request against the project's Statement of Work.

It determines:

- classification
- reasoning
- matched SOW item
- estimated effort
- estimate confidence

The agent is given the SOW context and project history.

---

### 3. Decision Agent

The Decision Agent determines whether the freelancer needs to be interrupted.

It also assigns:

- `LOW`
- `MEDIUM`
- `HIGH`

risk.

The agent has access to a **ledger lookup tool** that lets it retrieve current project numbers such as:

- accumulated unbilled hours
- accumulated unbilled cost
- scope-creep request count
- remaining revision slots

This means the agent can determine what project information it needs before making its risk assessment.

---

### 4. Communication Agent

The Communication Agent generates three client-facing response options:

- **Bill it**
- **Negotiate it**
- **Decline it**

The human remains in control of the final decision.

---

# Architecture

```text
                         ┌───────────────────────┐
                         │      Client Email     │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │      Gmail API        │
                         │    OAuth / Read-only  │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │   Gmail Pre-filter    │
                         │  Remove obvious spam  │
                         │  / automated mail     │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │     Intake Agent      │
                         │       Strands         │
                         │  Client request?      │
                         └───────────┬───────────┘
                                     │
                            genuine request
                                     │
                                     ▼
┌───────────────────────┐  ┌───────────────────────┐
│   Statement of Work   │─▶│      Scope Agent      │
│         SOW           │  │       Strands         │
└───────────────────────┘  └───────────┬───────────┘
                                      │
                                      ▼
                           classification + effort
                                      │
                                      ▼
                         ┌───────────────────────┐
                         │    Decision Agent     │
                         │       Strands         │
                         │   + Ledger Tool       │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │ Communication Agent   │
                         │       Strands         │
                         └───────────┬───────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
                   Bill It       Negotiate       Decline
                      │              │              │
                      └──────────────┼──────────────┘
                                     ▼
                              Human Decision
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │     Scope Ledger      │
                         │ Persistent History    │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │       Dashboard       │
                         │ Risk / Cost / History │
                         └───────────────────────┘