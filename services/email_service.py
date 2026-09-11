"""
Email ingestion service for Scope Creep Sentinel.

This version is a local email simulator. It represents the shape of an
incoming client email and extracts the content that should be analyzed.

Later, this can be replaced by a Gmail/Outlook connector without changing
the core Scope Agent, Decision Agent, or Scope Ledger workflow.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IncomingClientEmail(BaseModel):
    """Represents one incoming client email."""

    sender: str = Field(
        description="Email address or name of the client."
    )

    subject: str = Field(
        description="Subject line of the email."
    )

    body: str = Field(
        description="Full text of the client email."
    )


class EmailService:
    """Extracts a client request from an incoming email."""

    @staticmethod
    def extract_request(email: IncomingClientEmail) -> str:
        """
        Convert an email into the request text consumed by ProjectState.

        Including the subject helps the agent understand the client's intent
        while the body contains the actual request.
        """

        subject = email.subject.strip()
        body = email.body.strip()

        if not body:
            raise ValueError("Email body must not be empty.")

        if subject:
            return f"Subject: {subject}\n\n{body}"

        return body