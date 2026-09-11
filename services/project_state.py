"""
Project State - orchestration layer tying the Scope Ledger and the three
agents together into the end-to-end workflow.
"""

from __future__ import annotations

from typing import Optional

from agents.communication_agent import CommunicationAgent
from agents.decision_agent import DecisionAgent
from agents.scope_agent import ScopeAgent

from models.scope_models import (
    ClientRequestRecord,
    Classification,
    DecisionOption,
    GeneratedMessages,
    ScopeAnalysisResult,
)

from services.scope_ledger import ScopeLedger


class RequestOutcome:
    """Everything produced for one incoming client request."""

    def __init__(
        self,
        analysis: ScopeAnalysisResult,
        estimated_cost: float,
        requires_decision: bool,
        risk_level: str,
        decision_reasoning: str,
        messages: GeneratedMessages | None,
        record: ClientRequestRecord,
    ):
        self.analysis = analysis
        self.estimated_cost = estimated_cost
        self.requires_decision = requires_decision
        self.risk_level = risk_level
        self.decision_reasoning = decision_reasoning
        self.messages = messages
        self.record = record


class ProjectState:
    def __init__(
        self,
        model,
        ledger: ScopeLedger,
        mock_mode: bool = False,
    ):
        self.ledger = ledger
        self.mock_mode = mock_mode

        if mock_mode:
            from agents.mock_agents import (
                MockCommunicationAgent,
                MockDecisionAgent,
                MockScopeAgent,
            )

            self.scope_agent = MockScopeAgent(ledger.sow)
            self.decision_agent = MockDecisionAgent(ledger)
            self.communication_agent = MockCommunicationAgent(
                ledger.sow
            )

        else:
            self.scope_agent = ScopeAgent(model, ledger.sow)
            self.decision_agent = DecisionAgent(model, ledger)
            self.communication_agent = CommunicationAgent(
                model,
                ledger.sow,
            )

    def handle_incoming_request(
        self,
        request_text: str,
        source: str = "manual",
        sender: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> RequestOutcome:

        analysis = self.scope_agent.analyze(
            request_text,
            self.ledger,
        )

        # Cost is deterministic Python math.
        cost = round(
            analysis.estimated_hours
            * self.ledger.sow.hourly_rate,
            2,
        )

        assessment = self.decision_agent.assess(
            request_text,
            analysis,
            cost,
        )

        messages = None

        if assessment.requires_user_decision:
            messages = self.communication_agent.draft_messages(
                request_text,
                analysis,
                cost,
            )

        record = ClientRequestRecord(
            request_text=request_text,

            # New source metadata
            source=source,
            sender=sender,
            subject=subject,

            classification=analysis.classification,
            reasoning=analysis.reasoning,
            matched_sow_item=analysis.matched_sow_item,
            estimated_hours=analysis.estimated_hours,
            estimated_cost=cost,
            requires_user_decision=assessment.requires_user_decision,
            risk_level=assessment.risk_level,
        )

        return RequestOutcome(
            analysis=analysis,
            estimated_cost=cost,
            requires_decision=assessment.requires_user_decision,
            risk_level=assessment.risk_level.value,
            decision_reasoning=assessment.agent_reasoning,
            messages=messages,
            record=record,
        )

    def finalize_decision(
        self,
        outcome: RequestOutcome,
        decision: DecisionOption | None,
        sent_message: str | None,
    ) -> None:

        outcome.record.user_decision = decision
        outcome.record.sent_message = sent_message

        # An IN_SCOPE revision consumes a revision slot.
        matched = (
            outcome.analysis.matched_sow_item or ""
        ).lower()

        if (
            outcome.analysis.classification
            == Classification.IN_SCOPE
            and "revision" in matched
        ):
            self.ledger.use_revision()

        self.ledger.add_request(outcome.record)