"""
API-facing request/response schemas.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from models.scope_models import Classification, DecisionOption, RiskLevel


class ProjectOverviewResponse(BaseModel):
    project_name: str
    hourly_rate: float
    revision_limit: int
    revisions_used: int
    revisions_remaining: int

    included_items: list[str]
    excluded_items: list[str]

    total_requests_logged: int

    # Cumulative scope-creep impact
    scope_creep_requests: int
    total_scope_creep_hours: float
    total_scope_creep_cost: float

    # Currently unbilled scope-creep impact
    accumulated_unbilled_hours: float
    accumulated_unbilled_cost: float

    billed_count: int
    negotiated_count: int
    declined_count: int


class IncomingRequestBody(BaseModel):
    request_text: str


class GeneratedMessagesResponse(BaseModel):
    bill_it: str
    negotiate_it: str
    decline_it: str


class AnalysisResponse(BaseModel):
    id: str
    request_text: str
    classification: Classification
    reasoning: str
    matched_sow_item: Optional[str] = None
    estimated_hours: float
    estimated_cost: float
    risk_level: RiskLevel
    decision_reasoning: str
    requires_decision: bool
    messages: Optional[GeneratedMessagesResponse] = None


class DecisionBody(BaseModel):
    decision: DecisionOption


class DecisionResponse(BaseModel):
    id: str
    decision: DecisionOption
    sent_message: str


class HistoryRecordResponse(BaseModel):
    id: str
    timestamp: str

    # Request source metadata
    source: str = "manual"
    sender: Optional[str] = None
    subject: Optional[str] = None

    request_text: str
    classification: Classification
    reasoning: str
    matched_sow_item: Optional[str] = None
    estimated_hours: float
    estimated_cost: float
    requires_user_decision: bool
    risk_level: RiskLevel
    user_decision: Optional[DecisionOption] = None
    sent_message: Optional[str] = None


class HistoryResponse(BaseModel):
    records: list[HistoryRecordResponse]
    summary: ProjectOverviewResponse