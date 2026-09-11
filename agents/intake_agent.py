"""
Gmail Intake Agent.

Determines whether an incoming email appears to contain a genuine
client/project request that should proceed to Scope Creep analysis.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from strands import Agent

from services.email_service import IncomingClientEmail


class IntakeAssessment(BaseModel):
    """Structured result from the Gmail intake agent."""

    is_client_request: bool = Field(
        description=(
            "True when the email appears to be a genuine client/project "
            "request that may affect project scope, deliverables, features, "
            "revisions, timeline, effort, or cost."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence from 0.0 to 1.0 that the email is a genuine "
            "client/project request."
        ),
    )

    reasoning: str = Field(
        description=(
            "Brief explanation of why the email is or is not a client "
            "project request."
        )
    )

    request_focus: str = Field(
        description=(
            "Short description of the project request when one exists. "
            "Use an empty string when there is no project request."
        )
    )


SYSTEM_PROMPT = """You are the Gmail Intake Agent for Scope Creep Sentinel.

Your job is to decide whether an incoming email should enter the project's
scope-analysis workflow.

Treat an email as a CLIENT REQUEST when it contains a genuine request,
change, question, addition, modification, or instruction related to an
ongoing client project.

Examples that SHOULD be treated as client requests:
- "Can you add a mobile app?"
- "Could we add a loyalty program?"
- "Please change the checkout flow."
- "Can we add another page?"
- "Can you make the button work differently?"
- "We need one more revision."
- "Can you integrate another payment provider?"

Examples that should NOT be treated as client requests:
- Newsletters
- Marketing emails
- Promotional offers
- Payment reminders unrelated to a project change
- Automated deployment notifications
- Security alerts
- Performance reports
- Verification emails
- Social notifications
- General product announcements
- Personal messages unrelated to the project

Use the email subject and body together.

Do not decide whether a request is IN_SCOPE, GRAY_AREA, or OUT_OF_SCOPE.
That is the job of the Scope Agent.

Do not estimate hours or cost.
That is also the job of the Scope Agent.

Your only responsibility is determining whether this email should be
forwarded to the project scope-analysis workflow.
"""


class IntakeAgent:
    """Strands-powered email relevance classifier."""

    def __init__(self, model):
        self._agent = Agent(
            model=model,
            system_prompt=SYSTEM_PROMPT,
        )

    def assess(
        self,
        email: IncomingClientEmail,
    ) -> IntakeAssessment:
        prompt = (
            "Evaluate this incoming email.\n\n"
            f"From: {email.sender}\n"
            f"Subject: {email.subject}\n\n"
            f"Body:\n{email.body}\n\n"
            "Determine whether it is a genuine client/project request."
        )

        result = self._agent(
            prompt,
            structured_output_model=IntakeAssessment,
        )

        structured = result.structured_output

        if structured is None:
            raise RuntimeError(
                "Intake Agent did not return structured output."
            )

        if isinstance(structured, IntakeAssessment):
            return structured

        return IntakeAssessment.model_validate(structured)