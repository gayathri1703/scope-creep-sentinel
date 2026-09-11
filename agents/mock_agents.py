"""
Mock agents - deterministic, keyword-based stand-ins for the real
Strands/Bedrock-powered agents. Used only when config.MOCK_MODE is True,
so the whole application can be developed and tested without any
Bedrock/AWS access.

Each mock class implements the EXACT SAME method signature as its real
counterpart:
    MockScopeAgent.analyze(request_text, ledger)      == ScopeAgent.analyze
    MockDecisionAgent.assess(request_text, analysis, cost)  == DecisionAgent.assess
    MockCommunicationAgent.draft_messages(request_text, analysis, cost)  == CommunicationAgent.draft_messages

and returns the same Pydantic models (ScopeAnalysisResult, DecisionAssessment,
GeneratedMessages). Because of that, services/project_state.py's workflow
code is completely unaware of which pair of agents it's using - mock or
real - and the Scope Ledger gets updated exactly the same way either way.
"""

from __future__ import annotations

from models.scope_models import (
    Classification,
    DecisionAssessment,
    GeneratedMessages,
    RiskLevel,
    ScopeAnalysisResult,
    StatementOfWork,
)
from services.scope_ledger import ScopeLedger

# Hand-tuned responses for the three required demo scenarios, so they
# always produce exactly the specified result regardless of generic
# keyword-matching edge cases.
_DEMO_RESPONSES: dict[str, dict] = {
    "mobile app": dict(
        classification=Classification.OUT_OF_SCOPE,
        reasoning="Mobile application is explicitly excluded from the SOW.",
        matched_sow_item="Mobile application",
        estimated_hours=25,
        estimate_confidence="high",
    ),
    "checkout button": dict(
        classification=Classification.IN_SCOPE,
        reasoning="Adjusting an existing checkout page element falls under "
        "the included 'Checkout' deliverable.",
        matched_sow_item="Checkout",
        estimated_hours=1.5,
        estimate_confidence="high",
    ),
    "newsletter": dict(
        classification=Classification.GRAY_AREA,
        reasoning="A newsletter signup section isn't explicitly listed, but "
        "is plausibly a small addition to an existing page rather than a "
        "new deliverable - needs a judgment call.",
        matched_sow_item="5 website pages",
        estimated_hours=4,
        estimate_confidence="medium",
    ),
}


class MockScopeAgent:
    def __init__(self, sow: StatementOfWork):
        self.sow = sow

    def analyze(self, request_text: str, ledger: ScopeLedger) -> ScopeAnalysisResult:
        text = request_text.lower()

        for keyword, fields in _DEMO_RESPONSES.items():
            if keyword in text:
                return ScopeAnalysisResult(**fields)

        return self._generic_classify(text)

    def _generic_classify(self, text: str) -> ScopeAnalysisResult:
        for item in self.sow.excluded_items:
            if self._matches(item, text):
                return ScopeAnalysisResult(
                    classification=Classification.OUT_OF_SCOPE,
                    reasoning=f"This relates to '{item}', which is explicitly excluded from the SOW.",
                    matched_sow_item=item,
                    estimated_hours=12,
                    estimate_confidence="low",
                )

        for item in self.sow.included_items:
            if self._matches(item, text):
                return ScopeAnalysisResult(
                    classification=Classification.IN_SCOPE,
                    reasoning=f"This matches the included deliverable '{item}'.",
                    matched_sow_item=item,
                    estimated_hours=2,
                    estimate_confidence="low",
                )

        return ScopeAnalysisResult(
            classification=Classification.GRAY_AREA,
            reasoning="This request doesn't clearly match an included or "
            "excluded SOW item - needs a judgment call.",
            matched_sow_item=None,
            estimated_hours=5,
            estimate_confidence="low",
        )

    @staticmethod
    def _matches(sow_item: str, text: str) -> bool:
        keywords = [w for w in sow_item.lower().replace("/", " ").split() if len(w) > 3]
        return any(word in text for word in keywords)


class MockDecisionAgent:
    def __init__(self, ledger: ScopeLedger):
        self.ledger = ledger

    def assess(self, request_text: str, analysis: ScopeAnalysisResult, estimated_cost: float) -> DecisionAssessment:
        if analysis.classification == Classification.IN_SCOPE:
            return DecisionAssessment(
                requires_user_decision=False,
                risk_level=RiskLevel.LOW,
                agent_reasoning="Matches an included SOW item within limits - no decision needed.",
            )

        summary = self.ledger.summary()
        accumulated = summary["accumulated_unbilled_cost"]

        if analysis.classification == Classification.OUT_OF_SCOPE or (accumulated + estimated_cost) > 500:
            risk = RiskLevel.HIGH
        else:
            risk = RiskLevel.MEDIUM

        reasoning = (
            f"This request is {analysis.classification.value.replace('_', ' ').lower()}. "
            f"The project already has ${accumulated:.2f} in accumulated unbilled scope "
            f"creep, so this needs a decision from the freelancer."
        )
        return DecisionAssessment(requires_user_decision=True, risk_level=risk, agent_reasoning=reasoning)


class MockCommunicationAgent:
    def __init__(self, sow: StatementOfWork):
        self.sow = sow

    def draft_messages(self, request_text: str, analysis: ScopeAnalysisResult, estimated_cost: float) -> GeneratedMessages:
        hours = analysis.estimated_hours
        rate = self.sow.hourly_rate

        return GeneratedMessages(
            bill_it=(
                f"Thanks for the request! This falls outside the current project "
                f"scope, so I'd bill it as an add-on: roughly {hours} hours at "
                f"${rate}/hour (~${estimated_cost:.2f}). Let me know if you'd like me to go ahead."
            ),
            negotiate_it=(
                f"Happy to talk this through - it's outside the current phase's "
                f"scope, so let's discuss the extra effort (~{hours} hours) and "
                f"timeline before committing to anything."
            ),
            decline_it=(
                f"Thanks for the suggestion! This isn't included in the current "
                f"project scope, so I won't be able to fit it into this phase - "
                f"happy to revisit it for a future phase."
            ),
        )