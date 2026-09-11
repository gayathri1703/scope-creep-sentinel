"""
Gmail integration for Scope Creep Sentinel.

Reads Gmail messages using Google OAuth and converts them into the
existing IncomingClientEmail format.
"""

from __future__ import annotations

import base64
import os
from email.utils import parseaddr
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

from services.email_service import IncomingClientEmail


PROJECT_ROOT = Path(__file__).parent.parent

CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"

# Read-only Gmail access.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
]

# Default Gmail search query.
#
# We start with unread inbox mail and exclude common Gmail categories
# that are unlikely to contain client requests.
DEFAULT_GMAIL_QUERY = (
    "in:inbox "
    "is:unread "
    "-category:promotions "
    "-category:social "
    "-category:updates "
    "-category:forums"
)


class GmailService:
    """Small Gmail API wrapper for reading incoming client emails."""

    def __init__(self) -> None:
        self._service = self._build_service()

    def _build_service(self) -> Any:
        """
        Load an existing OAuth token or start the desktop OAuth flow.
        """

        credentials: Credentials | None = None

        if TOKEN_PATH.exists():
            credentials = Credentials.from_authorized_user_file(
                str(TOKEN_PATH),
                SCOPES,
            )

        if (
            credentials
            and credentials.expired
            and credentials.refresh_token
        ):
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            if not CREDENTIALS_PATH.exists():
                raise FileNotFoundError(
                    f"Missing Gmail OAuth credentials: {CREDENTIALS_PATH}"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH),
                SCOPES,
            )

            credentials = flow.run_local_server(
                port=0,
                access_type="offline",
                prompt="consent",
            )

            TOKEN_PATH.write_text(
                credentials.to_json(),
                encoding="utf-8",
            )

        return build(
            "gmail",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

    def list_unread_messages(
        self,
        max_results: int = 10,
    ) -> list[IncomingClientEmail]:
        """
        Return likely client emails from the unread inbox.

        The Gmail query can be overridden with the
        GMAIL_CLIENT_QUERY environment variable.
        """

        query = os.environ.get(
            "GMAIL_CLIENT_QUERY",
            DEFAULT_GMAIL_QUERY,
        ).strip()

        response = (
            self._service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
            )
            .execute()
        )

        messages = response.get("messages", [])

        results: list[IncomingClientEmail] = []

        for message in messages:
            message_id = message.get("id")

            if not message_id:
                continue

            full_message = (
                self._service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            )

            email = self._parse_message(full_message)

            if (
                email is not None
                and self._is_likely_client_email(email)
            ):
                results.append(email)

        return results

    def _is_likely_client_email(
        self,
        email: IncomingClientEmail,
    ) -> bool:
        """
        Reject obvious automated/newsletter messages before they reach
        the Strands analysis workflow.

        This is only a pre-filter. The agent will make the final decision
        about whether a candidate contains a project-related request.
        """

        sender = email.sender.lower().strip()
        subject = email.subject.lower().strip()

        automated_sender_markers = (
            "no-reply",
            "noreply",
            "notifications",
            "notification",
            "mailer-daemon",
            "donotreply",
            "do-not-reply",
        )

        automated_subject_markers = (
            "unsubscribe",
            "newsletter",
            "payment reminder",
            "performance report",
            "deployment",
            "verification code",
            "security alert",
            "your bill",
            "your invoice",
            "weekly digest",
            "monthly digest",
        )

        if any(
            marker in sender
            for marker in automated_sender_markers
        ):
            return False

        if any(
            marker in subject
            for marker in automated_subject_markers
        ):
            return False

        return True

    def _parse_message(
        self,
        message: dict[str, Any],
    ) -> IncomingClientEmail | None:
        """
        Convert a Gmail message payload into IncomingClientEmail.
        """

        payload = message.get("payload", {})
        headers = payload.get("headers", [])

        sender = ""
        subject = ""

        for header in headers:
            name = header.get("name", "").lower()
            value = header.get("value", "")

            if name == "from":
                sender = parseaddr(value)[1] or value

            elif name == "subject":
                subject = value

        body = self._extract_body(payload)

        if not body.strip():
            return None

        return IncomingClientEmail(
            sender=sender or "unknown@example.com",
            subject=subject or "(No subject)",
            body=body.strip(),
        )

    def _extract_body(
        self,
        payload: dict[str, Any],
    ) -> str:
        """
        Extract plain-text email content.

        Prefer text/plain when available.
        """

        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data")

        if body_data and (
            mime_type == "text/plain"
            or not payload.get("parts")
        ):
            return self._decode_body(body_data)

        for part in payload.get("parts", []):
            part_type = part.get("mimeType", "")

            if part_type == "text/plain":
                part_data = (
                    part.get("body", {})
                    .get("data")
                )

                if part_data:
                    return self._decode_body(part_data)

            nested_parts = part.get("parts")

            if nested_parts:
                nested_payload = {
                    "parts": nested_parts,
                }

                nested_text = self._extract_body(
                    nested_payload
                )

                if nested_text.strip():
                    return nested_text

        return ""

    @staticmethod
    def _decode_body(data: str) -> str:
        """
        Decode Gmail's URL-safe base64 message body.
        """

        padding = "=" * (
            (-len(data)) % 4
        )

        decoded = base64.urlsafe_b64decode(
            data + padding
        )

        return decoded.decode(
            "utf-8",
            errors="replace",
        )