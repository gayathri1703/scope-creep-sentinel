"""
Decision Agent - decides whether the freelancer actually needs to be
interrupted, and assigns a risk level, by considering not just this one
request but the project's accumulated scope-creep history.

This agent is given a TOOL that lets it look up ledger numbers itself
(accumulated unbilled hours/cost, scope-creep count, revisions remaining)
instead of us pre-computing everything into the prompt. That tool call is
the "genuine agent" part: the agent decides what it needs to check.

NOTE ON UNCERTAINTY: structured_output() is a confirmed, current Strands
API. What I could not verify against your exact installed version is
whether a single structured_output() call on an agent that also has tools
attached will invoke those tools before returning the schema. If you find
get_scope_creep_summary is never actually called once Bedrock access is
restored, replace assess() with:
    self._agent(prompt)  # a normal turn, free to call tools
    return self._agent.structured_output(
        DecisionAssessment, "Now give your final assessment as structured output."
    )
"""

from __future__ import annotations

from strands import Agent, tool

from models.scope_models import DecisionAssessment, ScopeAnalysisResult
from services.scope_ledger import ScopeLedger

SYSTEM_PROMPT = """You are the Decision Agent for a freelancer's project.

You receive a client request that the Scope Agent has already classified,
along with its estimated hours and cost. Decide:

1. Does the FREELANCER need to be interrupted to make a BILL / NEGOTIATE /
   DECLINE decision? A request that is clearly IN_SCOPE and within limits
   should NOT require a decision - just log it. GRAY_AREA and OUT_OF_SCOPE
   requests almost always require a decision.
2. What is the risk level (LOW / MEDIUM / HIGH)? Consider not just this
   request's cost but the project's accumulated unbilled scope creep -
   call the get_scope_creep_summary tool to check the ledger before
   deciding. A small request on top of a lot of existing unbilled creep is
   higher risk than the same request on a clean project.

Always call get_scope_creep_summary at least once before answering."""


class DecisionAgent:
    def __init__(self, model, ledger: ScopeLedger):
        self.ledger = ledger
        self._agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[self._make_summary_tool()],
        )

    def _make_summary_tool(self):
        ledger = self.ledger

        @tool
        def get_scope_creep_summary() -> dict:
            """Look up the project's current scope-ledger numbers before
            assessing risk: how many scope-creep requests have been logged,
            how many unbilled hours/dollars have accumulated, and how many
            revision slots remain.

            Returns:
                A dictionary with scope_creep_requests, accumulated_unbilled_hours,
                accumulated_unbilled_cost, and revisions_remaining.
            """
            s = ledger.summary()
            payload = {
                "scope_creep_requests": s["scope_creep_requests"],
                "accumulated_unbilled_hours": s["accumulated_unbilled_hours"],
                "accumulated_unbilled_cost": s["accumulated_unbilled_cost"],
                "revisions_remaining": s["revisions_remaining"],
            }
            return {"status": "success", "content": [{"text": str(payload)}]}

        return get_scope_creep_summary

    def assess(
        self,
        request_text: str,
        analysis: ScopeAnalysisResult,
        estimated_cost: float,
    ) -> DecisionAssessment:
        prompt = (
            f'Client request: "{request_text}"\n'
            f"Scope Agent classification: {analysis.classification.value}\n"
            f"Scope Agent reasoning: {analysis.reasoning}\n"
            f"Estimated additional hours: {analysis.estimated_hours}\n"
            f"Estimated additional cost: ${estimated_cost:.2f}\n\n"
            "Check the ledger, then decide if the freelancer needs to make "
            "a decision, and assess the risk level."
        )
        return self._agent.structured_output(DecisionAssessment, prompt)