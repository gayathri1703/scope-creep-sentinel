"""
Scope Agent - reads the SOW + recent project history and classifies an
incoming client request as IN_SCOPE / GRAY_AREA / OUT_OF_SCOPE, plus a
rough effort estimate.

The agent is deliberately strict about the contract:
- It may only call something "explicitly excluded" when it appears in
  the SOW's excluded items.
- It must distinguish contract facts from its own reasoning.
- It uses recent history as supporting context, not as a replacement
  for the current SOW.
- Transient model failures such as HTTP 503 are retried automatically.
"""

from __future__ import annotations

import time

from strands import Agent

from models.scope_models import ScopeAnalysisResult, StatementOfWork
from services.scope_ledger import ScopeLedger


SYSTEM_PROMPT_TEMPLATE = """You are the Scope Agent for a freelancer's project
called "{project_name}".

Your job is to analyze ONE incoming client request against the current
Statement of Work (SOW) and recent project history.

You must be contract-aware, conservative, and fact-based.

# CURRENT STATEMENT OF WORK

INCLUDED ITEMS:
{included}

EXPLICITLY EXCLUDED ITEMS:
{excluded}

REVISION LIMIT:
{revisions_used}/{revision_limit} revisions used
{revisions_remaining} revision(s) remaining

# RECENT PROJECT HISTORY

{history}

# CLASSIFICATION RULES

Choose exactly one classification:

1. IN_SCOPE
Use IN_SCOPE only when the request clearly matches an item that is
included in the SOW.

If the request is a revision request:
- classify it as IN_SCOPE only when a revision slot remains.
- if no revision slot remains, do NOT classify it as IN_SCOPE.

2. GRAY_AREA
Use GRAY_AREA when the request is plausibly related to the agreed
deliverables but the SOW does not clearly establish that it is included.

Examples:
- a meaningful enhancement to an included feature
- a request whose size or interpretation is ambiguous
- work that could reasonably be considered an extension of an included item

3. OUT_OF_SCOPE
Use OUT_OF_SCOPE when:
- the request matches an item explicitly listed in EXPLICITLY EXCLUDED ITEMS, OR
- the request is clearly unrelated to the deliverables listed in the SOW.

IMPORTANT:
Never say a request is "explicitly excluded" unless the requested item
actually appears in the EXPLICITLY EXCLUDED ITEMS list.

If something is simply not mentioned in the SOW, say that it is
"not clearly included" rather than calling it explicitly excluded.

# REASONING RULES

Your reasoning must:
- reference the most relevant SOW item when possible
- clearly distinguish what the contract actually says from your inference
- be concise and understandable to a freelancer
- avoid inventing contract terms, prices, deadlines, or exclusions
- avoid claiming that a client request is included merely because it is
  related to the project

# EFFORT ESTIMATION

Estimate the additional work required for THIS REQUEST only.

The estimate should be a reasonable engineering estimate based on:
- the request itself
- the SOW
- similar requests in recent history

Do not include work that is already part of the existing SOW unless
the new request genuinely adds extra effort.

Return a numeric estimate in hours.

# HISTORY RULE

Recent project history is supporting evidence only.

Do not assume an earlier decision automatically applies to the new request.
Analyze every new request against the CURRENT SOW first.

# OUTPUT

Return a structured ScopeAnalysisResult.

Populate:
- classification
- reasoning
- matched_sow_item
- estimated_hours
- estimate_confidence

For matched_sow_item:
- use the most relevant included/excluded SOW item when there is a clear match
- otherwise use null rather than inventing a contract item

For estimate_confidence:
- use exactly one of: low, medium, high

Incoming client request:
"{request_text}"
"""


def _format_history(ledger: ScopeLedger, limit: int = 5) -> str:
    """Format recent history for the agent without overloading context."""

    if not ledger.history:
        return "(no previous client requests logged yet)"

    lines: list[str] = []

    for record in ledger.history[-limit:]:
        decision = (
            record.user_decision.value
            if record.user_decision
            else "n/a"
        )

        lines.append(
            f'- "{record.request_text}" -> '
            f"{record.classification.value} "
            f"(~{record.estimated_hours}h, "
            f"decision: {decision})"
        )

    return "\n".join(lines)


def _is_transient_model_error(error: Exception) -> bool:
    """
    Identify temporary provider failures that are worth retrying.

    We deliberately retry only transient availability/rate-limit style
    errors, not validation/authentication/configuration errors.
    """

    message = str(error).upper()

    transient_markers = (
        "503",
        "UNAVAILABLE",
        "429",
        "RESOURCE_EXHAUSTED",
        "RATE LIMIT",
        "TOO MANY REQUESTS",
        "OVERLOADED",
    )

    return any(marker in message for marker in transient_markers)


class ScopeAgent:
    """Strands agent responsible for SOW-aware request classification."""

    def __init__(self, model, sow: StatementOfWork):
        self.sow = sow
        self._model = model

    def _build_agent(self, ledger: ScopeLedger) -> Agent:
        """
        Build a fresh agent for every request so the SOW and history are
        always current.
        """

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            project_name=self.sow.project_name,
            included=(
                "\n".join(
                    f"- {item}"
                    for item in self.sow.included_items
                )
                or "(none)"
            ),
            excluded=(
                "\n".join(
                    f"- {item}"
                    for item in self.sow.excluded_items
                )
                or "(none)"
            ),
            revisions_used=self.sow.revisions_used,
            revision_limit=self.sow.revision_limit,
            revisions_remaining=ledger.revisions_remaining(),
            history=_format_history(ledger),
            request_text="{request_text}",
        )

        return Agent(
            model=self._model,
            system_prompt=system_prompt,
        )

    def analyze(
        self,
        request_text: str,
        ledger: ScopeLedger,
    ) -> ScopeAnalysisResult:
        """Analyze one incoming client request with transient-error retries."""

        agent = self._build_agent(ledger)

        prompt = (
            "Analyze this incoming client request strictly against "
            "the current SOW and return the required structured result:\n\n"
            f'"{request_text}"'
        )

        max_attempts = 3

        for attempt in range(1, max_attempts + 1):
            try:
                return agent.structured_output(
                    ScopeAnalysisResult,
                    prompt,
                )

            except Exception as error:
                if (
                    attempt == max_attempts
                    or not _is_transient_model_error(error)
                ):
                    raise

                # Exponential backoff:
                # attempt 1 -> 1 second
                # attempt 2 -> 2 seconds
                delay = 2 ** (attempt - 1)

                print(
                    f"Transient model error detected. "
                    f"Retrying in {delay}s "
                    f"(attempt {attempt}/{max_attempts})..."
                )

                time.sleep(delay)

        # Defensive fallback; the loop either returns or raises.
        raise RuntimeError("Scope analysis failed unexpectedly.")