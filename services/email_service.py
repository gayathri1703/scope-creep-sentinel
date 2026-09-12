"""
Email ingestion service for Scope Creep Sentinel.

This module defines the common email shape used by the simulated email
flow and the real Gmail connector.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class IncomingClientEmail(BaseModel):
    """Represents one incoming client email."""

    message_id: str | None = Field(
        default=None,
        description="Provider message ID, such as a Gmail message ID.",
    )

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
    def extract_request(
        email: IncomingClientEmail,
    ) -> str:
        """
        Convert an email into the request text consumed by ProjectState.

        Including the subject helps the agent understand the client's intent
        while the body contains the actual request.
        """

        subject = email.subject.strip()
        body = email.body.strip()

        if not body:
            raise ValueError(
                "Email body must not be empty."
            )

        if subject:
            return (
                f"Subject: {subject}\n\n{body}"
            )

        return body