"""
Unit tests for ScopeLedger. Deliberately do NOT touch Strands/Bedrock -
these need live AWS access which shouldn't gate your test suite.

Run with: pytest tests/test_scope_ledger.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.scope_models import (
    ClientRequestRecord,
    Classification,
    DecisionOption,
    RiskLevel,
    StatementOfWork,
)
from services.scope_ledger import ScopeLedger


def make_ledger(tmp_path: Path) -> ScopeLedger:
    sow = StatementOfWork(
        project_name="Test Project",
        included_items=["5 pages", "Shopping cart"],
        excluded_items=["Mobile app"],
        revision_limit=2,
        revisions_used=0,
        hourly_rate=75,
    )
    return ScopeLedger(sow=sow, history_path=tmp_path / "history.json")


def make_record(**overrides) -> ClientRequestRecord:
    defaults = dict(
        request_text="Add a mobile app",
        classification=Classification.OUT_OF_SCOPE,
        reasoning="Mobile app explicitly excluded.",
        matched_sow_item="Mobile app",
        estimated_hours=20,
        estimated_cost=1500,
        requires_user_decision=True,
        risk_level=RiskLevel.HIGH,
    )
    defaults.update(overrides)
    return ClientRequestRecord(**defaults)


def test_empty_ledger_summary(tmp_path):
    ledger = make_ledger(tmp_path)
    summary = ledger.summary()
    assert summary["total_requests_logged"] == 0
    assert summary["accumulated_unbilled_cost"] == 0


def test_unbilled_scope_creep_accumulates(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.add_request(make_record())
    ledger.add_request(
        make_record(request_text="Add analytics", estimated_hours=10, estimated_cost=750)
    )

    assert ledger.scope_creep_request_count() == 2
    assert ledger.accumulated_unbilled_hours() == 30
    assert ledger.accumulated_unbilled_cost() == 2250


def test_billed_request_not_counted_as_unbilled(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.add_request(make_record(user_decision=DecisionOption.BILL_IT))
    assert ledger.accumulated_unbilled_hours() == 0


def test_in_scope_request_ignored_by_scope_creep_counters(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.add_request(
        make_record(
            classification=Classification.IN_SCOPE,
            reasoning="Matches shopping cart item.",
            matched_sow_item="Shopping cart",
            requires_user_decision=False,
            risk_level=RiskLevel.LOW,
        )
    )
    assert ledger.scope_creep_request_count() == 0


def test_history_persists_and_reloads(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.add_request(make_record())

    reloaded = ScopeLedger(sow=ledger.sow, history_path=ledger.history_path)
    assert len(reloaded.history) == 1
    assert reloaded.history[0].request_text == "Add a mobile app"


def test_requests_by_decision(tmp_path):
    ledger = make_ledger(tmp_path)
    ledger.add_request(make_record(user_decision=DecisionOption.NEGOTIATE_IT))
    ledger.add_request(
        make_record(user_decision=DecisionOption.DECLINE_IT, request_text="Add SEO")
    )

    assert len(ledger.requests_by_decision(DecisionOption.NEGOTIATE_IT)) == 1
    assert len(ledger.requests_by_decision(DecisionOption.DECLINE_IT)) == 1