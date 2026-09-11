"""
Domain models for Scope Creep Sentinel.

These Pydantic models do double duty:
1. Plain data containers used by the Scope Ledger (SOW, request records).
2. "Structured output" schemas handed directly to Strands agents via
   agent.structured_output(SchemaModel, prompt).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class Classification(str, Enum):
    IN_SCOPE = "IN_SCOPE"
    GRAY_AREA = "GRAY_AREA"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class DecisionOption(str, Enum):
    BILL_IT = "BILL_IT"
    NEGOTIATE_IT = "NEGOTIATE_IT"
    DECLINE_IT = "DECLINE_IT"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class StatementOfWork(BaseModel):
    """The project's SOW."""

    project_name: str
    included_items: list[str]
    excluded_items: list[str]
    revision_limit: int
    revisions_used: int = 0
    hourly_rate: float = Field(gt=0)


class ScopeAnalysisResult(BaseModel):
    """Structured output schema for the Scope Agent."""

    classification: Classification = Field(
        description=(
            "IN_SCOPE, GRAY_AREA, or OUT_OF_SCOPE relative to "
            "the SOW's included/excluded items and revision limit."
        )
    )

    reasoning: str = Field(
        description=(
            "Short, specific explanation referencing the SOW item(s) "
            "that led to this classification."
        )
    )

    matched_sow_item: Optional[str] = Field(
        default=None,
        description=(
            "The specific included/excluded SOW line item this "
            "request relates to, if any."
        ),
    )

    estimated_hours: float = Field(
        ge=0,
        description=(
            "Realistic estimate of additional hours this request "
            "would take a freelance developer/designer."
        ),
    )

    estimate_confidence: str = Field(
        description="One of: low, medium, high."
    )


class DecisionAssessment(BaseModel):
    """Structured output schema for the Decision Agent."""

    requires_user_decision: bool = Field(
        description=(
            "False only when the request is clearly IN_SCOPE, "
            "within limits, with no scope-creep concern."
        )
    )

    risk_level: RiskLevel

    agent_reasoning: str = Field(
        description=(
            "Explanation that accounts for this request AND the "
            "project's accumulated unbilled scope-creep history."
        )
    )


class GeneratedMessages(BaseModel):
    """Structured output schema for the Communication Agent."""

    bill_it: str = Field(
        description="Client message billing the extra work as an add-on."
    )

    negotiate_it: str = Field(
        description="Client message proposing to discuss scope/timeline."
    )

    decline_it: str = Field(
        description="Polite client message declining the request for now."
    )


class ClientRequestRecord(BaseModel):
    """
    One row of project history.

    Source metadata is optional so existing requests created before
    email ingestion continue to load correctly.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Request content
    request_text: str

    # Where the request came from
    source: str = Field(
        default="manual",
        description="Origin of the request, e.g. manual or email.",
    )

    sender: Optional[str] = Field(
        default=None,
        description="Client sender when the request came from email.",
    )

    subject: Optional[str] = Field(
        default=None,
        description="Email subject when the request came from email.",
    )

    # Scope analysis
    classification: Classification
    reasoning: str
    matched_sow_item: Optional[str] = None
    estimated_hours: float
    estimated_cost: float
    requires_user_decision: bool
    risk_level: RiskLevel

    # Human decision
    user_decision: Optional[DecisionOption] = None
    sent_message: Optional[str] = None