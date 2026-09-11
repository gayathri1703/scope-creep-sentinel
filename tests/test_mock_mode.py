"""
Tests for MOCK_MODE.

These tests verify that the mock agents drive the same
ProjectState / ScopeLedger workflow without requiring
Bedrock, Gemini, AWS, or Gmail access.

Run with:
    pytest tests/test_mock_mode.py
"""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from models.scope_models import (
    Classification,
    DecisionOption,
    StatementOfWork,
)
from services.email_service import IncomingClientEmail
from services.project_state import ProjectState
from services.scope_ledger import ScopeLedger


def make_project(tmp_path: Path) -> ProjectState:
    sow = StatementOfWork(
        project_name="E-commerce Website",
        included_items=[
            "5 website pages",
            "Product listing",
            "Shopping cart",
            "Checkout",
            "2 rounds of revisions",
        ],
        excluded_items=[
            "Mobile application",
            "Payment gateway integration",
            "Advanced analytics",
        ],
        revision_limit=2,
        revisions_used=0,
        hourly_rate=75,
    )

    ledger = ScopeLedger(
        sow=sow,
        history_path=tmp_path / "history.json",
    )

    return ProjectState(
        model=None,
        ledger=ledger,
        mock_mode=True,
    )


def test_out_of_scope_mobile_app_example(tmp_path):
    project = make_project(tmp_path)

    outcome = project.handle_incoming_request(
        "Can you also build a mobile application for the website?"
    )

    assert outcome.analysis.classification == (
        Classification.OUT_OF_SCOPE
    )

    assert "excluded" in (
        outcome.analysis.reasoning.lower()
    )

    assert outcome.analysis.estimated_hours == 25
    assert outcome.estimated_cost == 25 * 75
    assert outcome.requires_decision is True
    assert outcome.messages is not None


def test_in_scope_example(tmp_path):
    project = make_project(tmp_path)

    outcome = project.handle_incoming_request(
        "Can you change the color of the checkout button?"
    )

    assert outcome.analysis.classification == (
        Classification.IN_SCOPE
    )

    assert outcome.requires_decision is False
    assert outcome.messages is None


def test_gray_area_example(tmp_path):
    project = make_project(tmp_path)

    outcome = project.handle_incoming_request(
        "Could you add a newsletter signup section to the homepage?"
    )

    assert outcome.analysis.classification == (
        Classification.GRAY_AREA
    )

    assert outcome.requires_decision is True


def test_mock_result_updates_the_real_ledger(tmp_path):
    project = make_project(tmp_path)

    outcome = project.handle_incoming_request(
        "Can you also build a mobile application for the website?"
    )

    assert len(project.ledger.history) == 0

    project.finalize_decision(
        outcome,
        decision=DecisionOption.NEGOTIATE_IT,
        sent_message="Let's talk.",
    )

    assert len(project.ledger.history) == 1

    saved = project.ledger.history[0]

    assert saved.classification == (
        Classification.OUT_OF_SCOPE
    )

    assert saved.user_decision == (
        DecisionOption.NEGOTIATE_IT
    )

    assert project.ledger.scope_creep_request_count() == 1

    reloaded = ScopeLedger(
        sow=project.ledger.sow,
        history_path=project.ledger.history_path,
    )

    assert len(reloaded.history) == 1


def test_generic_request_falls_back_to_sow_keyword_matching(
    tmp_path,
):
    project = make_project(tmp_path)

    outcome = project.handle_incoming_request(
        "Can you set up advanced analytics dashboards for us?"
    )

    assert outcome.analysis.classification == (
        Classification.OUT_OF_SCOPE
    )

    assert outcome.analysis.matched_sow_item == (
        "Advanced analytics"
    )


def test_mock_email_enters_project_workflow(tmp_path):
    project = make_project(tmp_path)

    email = IncomingClientEmail(
        sender="client@example.com",
        subject="New mobile app request",
        body=(
            "Could you also build a mobile application "
            "for the website?"
        ),
    )

    outcome = project.handle_incoming_email(email)

    assert outcome is not None

    assert outcome.record.source == "email"
    assert outcome.record.sender == "client@example.com"
    assert outcome.record.subject == "New mobile app request"

    assert outcome.analysis.classification == (
        Classification.OUT_OF_SCOPE
    )

    assert outcome.analysis.estimated_hours == 25
    assert outcome.estimated_cost == 25 * 75
    assert outcome.requires_decision is True


def test_mock_email_preserves_email_metadata_after_decision(
    tmp_path,
):
    project = make_project(tmp_path)

    email = IncomingClientEmail(
        sender="client@example.com",
        subject="Mobile application",
        body=(
            "Please build a mobile application "
            "for our website."
        ),
    )

    outcome = project.handle_incoming_email(email)

    assert outcome is not None

    project.finalize_decision(
        outcome,
        decision=DecisionOption.BILL_IT,
        sent_message="We can add this as additional work.",
    )

    saved = project.ledger.history[0]

    assert saved.source == "email"
    assert saved.sender == "client@example.com"
    assert saved.subject == "Mobile application"
    assert saved.user_decision == DecisionOption.BILL_IT