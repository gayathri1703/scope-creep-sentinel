"""
Scope Creep Sentinel - Web API.

The API drives the real ProjectState / ScopeLedger workflow.
The selected Strands model provider is controlled by config.MOCK_MODE
and config.MODEL_PROVIDER.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from api.schemas import (
    AnalysisResponse,
    DecisionBody,
    DecisionResponse,
    GeneratedMessagesResponse,
    HistoryRecordResponse,
    HistoryResponse,
    IncomingRequestBody,
    ProjectOverviewResponse,
)
from models.scope_models import DecisionOption
from services.email_service import EmailService, IncomingClientEmail
from services.project_state import ProjectState, RequestOutcome
from services.scope_ledger import ScopeLedger


WEB_DIR = Path(__file__).parent.parent / "web"


app = FastAPI(title="Scope Creep Sentinel API")

app.mount(
    "/web",
    StaticFiles(directory=WEB_DIR),
    name="web",
)


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

_ledger = ScopeLedger.load(
    sow_path=config.SOW_PATH,
    history_path=config.HISTORY_PATH,
)

_model = (
    None
    if config.MOCK_MODE
    else config.build_model()
)

_project = ProjectState(
    model=_model,
    ledger=_ledger,
    mock_mode=config.MOCK_MODE,
)

# Temporary bridge between analysis and human decision.
_pending_outcomes: dict[str, RequestOutcome] = {}


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/")
def serve_dashboard() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mock_mode": config.MOCK_MODE,
        "model_provider": config.MODEL_PROVIDER,
    }


# ---------------------------------------------------------------------------
# Project overview
# ---------------------------------------------------------------------------

def _overview_response() -> ProjectOverviewResponse:
    sow = _ledger.sow
    summary = _ledger.summary()

    return ProjectOverviewResponse(
        project_name=sow.project_name,
        hourly_rate=sow.hourly_rate,
        revision_limit=sow.revision_limit,
        revisions_used=sow.revisions_used,
        revisions_remaining=_ledger.revisions_remaining(),

        included_items=sow.included_items,
        excluded_items=sow.excluded_items,

        total_requests_logged=summary["total_requests_logged"],

        scope_creep_requests=summary["scope_creep_requests"],
        total_scope_creep_hours=summary["total_scope_creep_hours"],
        total_scope_creep_cost=summary["total_scope_creep_cost"],

        accumulated_unbilled_hours=summary[
            "accumulated_unbilled_hours"
        ],
        accumulated_unbilled_cost=summary[
            "accumulated_unbilled_cost"
        ],

        billed_count=summary["billed_count"],
        negotiated_count=summary["negotiated_count"],
        declined_count=summary["declined_count"],
    )


@app.get(
    "/api/project",
    response_model=ProjectOverviewResponse,
)
def get_project() -> ProjectOverviewResponse:
    return _overview_response()


# ---------------------------------------------------------------------------
# Shared analysis helper
# ---------------------------------------------------------------------------

def _analyze_request(
    request_text: str,
    source: str = "manual",
    sender: str | None = None,
    subject: str | None = None,
) -> AnalysisResponse:
    """
    Send request text through the existing ProjectState workflow.

    Source metadata is preserved so requests originating from email can be
    distinguished from manually submitted requests.
    """

    if not request_text.strip():
        raise HTTPException(
            status_code=400,
            detail="request_text must not be empty",
        )

    try:
        outcome = _project.handle_incoming_request(
            request_text=request_text,
            source=source,
            sender=sender,
            subject=subject,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Analysis failed: {e}",
        ) from e

    _pending_outcomes[outcome.record.id] = outcome

    messages = None

    if outcome.messages:
        messages = GeneratedMessagesResponse(
            bill_it=outcome.messages.bill_it,
            negotiate_it=outcome.messages.negotiate_it,
            decline_it=outcome.messages.decline_it,
        )

    return AnalysisResponse(
        id=outcome.record.id,
        request_text=outcome.record.request_text,
        classification=outcome.analysis.classification,
        reasoning=outcome.analysis.reasoning,
        matched_sow_item=outcome.analysis.matched_sow_item,
        estimated_hours=outcome.analysis.estimated_hours,
        estimated_cost=outcome.estimated_cost,
        risk_level=outcome.risk_level,
        decision_reasoning=outcome.decision_reasoning,
        requires_decision=outcome.requires_decision,
        messages=messages,
    )


# ---------------------------------------------------------------------------
# Manual request endpoint
# ---------------------------------------------------------------------------

@app.post(
    "/api/requests",
    response_model=AnalysisResponse,
)
def submit_request(
    body: IncomingRequestBody,
) -> AnalysisResponse:

    return _analyze_request(
        request_text=body.request_text,
        source="manual",
    )


# ---------------------------------------------------------------------------
# Client email endpoint
# ---------------------------------------------------------------------------

@app.post(
    "/api/emails",
    response_model=AnalysisResponse,
)
def submit_client_email(
    email: IncomingClientEmail,
) -> AnalysisResponse:
    """
    Simulate receiving an email from a client.

    The email subject and body are converted into the request text,
    while sender and subject are preserved as metadata on the
    ClientRequestRecord.
    """

    try:
        request_text = EmailService.extract_request(email)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    return _analyze_request(
        request_text=request_text,
        source="email",
        sender=email.sender,
        subject=email.subject,
    )


# ---------------------------------------------------------------------------
# Human decision
# ---------------------------------------------------------------------------

@app.post(
    "/api/requests/{request_id}/decision",
    response_model=DecisionResponse,
)
def submit_decision(
    request_id: str,
    body: DecisionBody,
) -> DecisionResponse:

    outcome = _pending_outcomes.pop(
        request_id,
        None,
    )

    if outcome is None:
        raise HTTPException(
            status_code=404,
            detail="No pending analysis found for that id",
        )

    message_map = {
        DecisionOption.BILL_IT: (
            outcome.messages.bill_it
            if outcome.messages
            else ""
        ),
        DecisionOption.NEGOTIATE_IT: (
            outcome.messages.negotiate_it
            if outcome.messages
            else ""
        ),
        DecisionOption.DECLINE_IT: (
            outcome.messages.decline_it
            if outcome.messages
            else ""
        ),
    }

    sent_message = message_map[body.decision]

    _project.finalize_decision(
        outcome,
        decision=body.decision,
        sent_message=sent_message,
    )

    return DecisionResponse(
        id=request_id,
        decision=body.decision,
        sent_message=sent_message,
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@app.get(
    "/api/history",
    response_model=HistoryResponse,
)
def get_history() -> HistoryResponse:

    records = [
        HistoryRecordResponse(
            id=r.id,
            timestamp=r.timestamp,

            # Email/manual source metadata
            source=r.source,
            sender=r.sender,
            subject=r.subject,

            request_text=r.request_text,
            classification=r.classification,
            reasoning=r.reasoning,
            matched_sow_item=r.matched_sow_item,
            estimated_hours=r.estimated_hours,
            estimated_cost=r.estimated_cost,
            requires_user_decision=r.requires_user_decision,
            risk_level=r.risk_level,
            user_decision=r.user_decision,
            sent_message=r.sent_message,
        )
        for r in _ledger.history
    ]

    return HistoryResponse(
        records=records,
        summary=_overview_response(),
    )