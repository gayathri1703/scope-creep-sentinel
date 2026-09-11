"""
Scope Ledger: the persistent memory of a project.

Deliberately NO LLM calls in this file. Financial calculations and
scope-creep totals are deterministic Python arithmetic so they remain
consistent and trustworthy.
"""

from __future__ import annotations

import json
from pathlib import Path

from models.scope_models import (
    ClientRequestRecord,
    Classification,
    DecisionOption,
    StatementOfWork,
)


class ScopeLedger:
    def __init__(self, sow: StatementOfWork, history_path: Path):
        self.sow = sow
        self.history_path = history_path
        self.history: list[ClientRequestRecord] = []
        self._load_history()

    # ---------- construction / persistence ----------

    @classmethod
    def load(cls, sow_path: Path, history_path: Path) -> "ScopeLedger":
        sow_data = json.loads(sow_path.read_text(encoding="utf-8"))
        sow = StatementOfWork.model_validate(sow_data)
        return cls(sow=sow, history_path=history_path)

    def _load_history(self) -> None:
        if self.history_path.exists():
            raw = json.loads(
                self.history_path.read_text(encoding="utf-8")
            )
            self.history = [
                ClientRequestRecord.model_validate(r)
                for r in raw
            ]

    def _save_history(self) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)

        data = [
            r.model_dump(mode="json")
            for r in self.history
        ]

        self.history_path.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8",
        )

    # ---------- writes ----------

    def add_request(self, record: ClientRequestRecord) -> None:
        self.history.append(record)
        self._save_history()

    def use_revision(self) -> None:
        self.sow.revisions_used += 1

    # ---------- scope-creep calculations ----------

    def scope_creep_requests(self) -> list[ClientRequestRecord]:
        """
        Return every request that went beyond the agreed scope.
        """
        return [
            r
            for r in self.history
            if r.classification != Classification.IN_SCOPE
        ]

    def scope_creep_request_count(self) -> int:
        return len(self.scope_creep_requests())

    def total_scope_creep_hours(self) -> float:
        """
        Total estimated additional work requested beyond the SOW.

        This includes scope-creep work whether it was billed,
        negotiated, or declined.
        """
        return round(
            sum(
                r.estimated_hours
                for r in self.scope_creep_requests()
            ),
            2,
        )

    def total_scope_creep_cost(self) -> float:
        """
        Estimated financial value of all scope-creep requests.
        """
        return round(
            self.total_scope_creep_hours()
            * self.sow.hourly_rate,
            2,
        )

    # ---------- unbilled calculations ----------

    def accumulated_unbilled_hours(self) -> float:
        """
        Scope-creep hours that have not been billed.

        A BILL_IT decision is excluded because the work has already
        been identified as billed.
        """
        return round(
            sum(
                r.estimated_hours
                for r in self.history
                if r.classification != Classification.IN_SCOPE
                and r.user_decision != DecisionOption.BILL_IT
            ),
            2,
        )

    def accumulated_unbilled_cost(self) -> float:
        return round(
            self.accumulated_unbilled_hours()
            * self.sow.hourly_rate,
            2,
        )

    # ---------- decision queries ----------

    def requests_by_decision(
        self,
        decision: DecisionOption,
    ) -> list[ClientRequestRecord]:
        return [
            r
            for r in self.history
            if r.user_decision == decision
        ]

    def revisions_remaining(self) -> int:
        return max(
            self.sow.revision_limit - self.sow.revisions_used,
            0,
        )

    # ---------- summary ----------

    def summary(self) -> dict:
        return {
            "project_name": self.sow.project_name,

            "total_requests_logged": len(self.history),

            # Scope-creep totals
            "scope_creep_requests": self.scope_creep_request_count(),
            "total_scope_creep_hours": self.total_scope_creep_hours(),
            "total_scope_creep_cost": self.total_scope_creep_cost(),

            # Currently unbilled scope creep
            "accumulated_unbilled_hours": (
                self.accumulated_unbilled_hours()
            ),
            "accumulated_unbilled_cost": (
                self.accumulated_unbilled_cost()
            ),

            # Decisions
            "negotiated_count": len(
                self.requests_by_decision(
                    DecisionOption.NEGOTIATE_IT
                )
            ),
            "declined_count": len(
                self.requests_by_decision(
                    DecisionOption.DECLINE_IT
                )
            ),
            "billed_count": len(
                self.requests_by_decision(
                    DecisionOption.BILL_IT
                )
            ),

            "revisions_remaining": self.revisions_remaining(),
        }