"""Section 6.4 — Daily Reconciliation checks."""

from datetime import date
from decimal import Decimal

from app.models.db import Agent, HourlyBreakdown, LeaveLedger, PendingApproval
from app.models.enums import (
    ContractType,
    LeaveType,
    OverspendPolicy,
    ReconciliationCheckType,
)
from app.services import reconciliation_service


def _agent(agent_id: str) -> Agent:
    return Agent(
        agent_id=agent_id,
        contract_type=ContractType.FULL_TIME,
        base_hourly_rate=Decimal("250"),
        min_monthly_pay=Decimal("35000"),
        max_monthly_pay=Decimal("70000"),
        weekly_contracted_hours=40,
        overtime_multiplier=Decimal("1.5"),
        holiday_multiplier=Decimal("2.0"),
        night_differential=Decimal("0.10"),
        currency="INR",
    )


def test_coverage_variance_flagged(db_session):
    db_session.add(_agent("A1"))
    db_session.add(
        HourlyBreakdown(
            agent_id="A1",
            date=date(2026, 4, 14),
            productive_minutes=Decimal("200"),
            available_minutes=Decimal("50"),
            break_minutes=Decimal("0"),
            training_minutes=Decimal("0"),
            scheduled_minutes=Decimal("480"),
            worked_minutes=Decimal("250"),  # >40% under
            overtime_minutes=Decimal("0"),
            is_holiday=False,
            night_minutes=Decimal("0"),
        )
    )
    db_session.commit()

    result = reconciliation_service.run(db_session, date(2026, 4, 14))
    assert result["coverage_findings"] == 1
    finding = result["findings"][0]
    assert finding.check_type == ReconciliationCheckType.COVERAGE


def test_pending_approval_blocks_close(db_session):
    db_session.add(_agent("A1"))
    db_session.add(
        LeaveLedger(
            agent_id="A1",
            leave_type=LeaveType.PAID,
            approved_balance=Decimal("0"),
            consumed_balance=Decimal("0"),
            overspend_policy=OverspendPolicy.MANAGER_APPROVAL,
            cycle_start=date(2026, 1, 1),
        )
    )
    db_session.add(
        PendingApproval(
            agent_id="A1",
            date=date(2026, 4, 10),
            leave_type=LeaveType.PAID,
            reason="Test pending",
        )
    )
    db_session.commit()

    result = reconciliation_service.run(db_session, date(2026, 4, 10))
    blocks = [f for f in result["findings"] if f.severity == "BLOCK"]
    assert len(blocks) >= 1
