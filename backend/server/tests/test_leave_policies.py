"""Section 6 — the three overspend policies."""

from datetime import date
from decimal import Decimal

from app.models.db import Agent, LeaveLedger, PendingApproval
from app.models.enums import (
    BillingStatus,
    ContractType,
    LeaveType,
    OverspendPolicy,
)
from app.services import leave_service


def _agent(agent_id: str = "A1") -> Agent:
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


def test_absence_within_balance_is_paid(db_session):
    agent = _agent()
    db_session.add(agent)
    db_session.add(
        LeaveLedger(
            agent_id=agent.agent_id,
            leave_type=LeaveType.PAID,
            approved_balance=Decimal("5"),
            consumed_balance=Decimal("0"),
            overspend_policy=OverspendPolicy.UNPAID_AUTO,
            cycle_start=date(2026, 1, 1),
        )
    )
    db_session.commit()

    res = leave_service.resolve(
        db_session,
        agent,
        date(2026, 4, 10),
        worked_minutes=Decimal("0"),
        scheduled_minutes=Decimal("480"),
        requested_leave_type=LeaveType.PAID,
    )
    db_session.commit()
    assert res.is_absence_day is True
    assert res.billing_status == BillingStatus.FINALIZED
    assert res.paid_from_balance_days == Decimal("1")
    # 1 day * 250 * (40/5) = 2000
    assert res.leave_pay == Decimal("2000")


def test_block_policy_returns_blocked(db_session):
    agent = _agent("BLOCKED_AGENT")
    db_session.add(agent)
    db_session.add(
        LeaveLedger(
            agent_id=agent.agent_id,
            leave_type=LeaveType.PAID,
            approved_balance=Decimal("0"),
            consumed_balance=Decimal("0"),
            overspend_policy=OverspendPolicy.BLOCK,
            cycle_start=date(2026, 1, 1),
        )
    )
    db_session.commit()

    res = leave_service.resolve(
        db_session,
        agent,
        date(2026, 4, 10),
        worked_minutes=Decimal("0"),
        scheduled_minutes=Decimal("480"),
        requested_leave_type=LeaveType.PAID,
    )
    assert res.billing_status == BillingStatus.BLOCKED
    assert res.blocked_reason is not None
    assert res.policy_applied == OverspendPolicy.BLOCK


def test_unpaid_auto_policy_records_lwp(db_session):
    agent = _agent("LWP_AGENT")
    db_session.add(agent)
    db_session.add(
        LeaveLedger(
            agent_id=agent.agent_id,
            leave_type=LeaveType.PAID,
            approved_balance=Decimal("0"),
            consumed_balance=Decimal("0"),
            overspend_policy=OverspendPolicy.UNPAID_AUTO,
            cycle_start=date(2026, 1, 1),
        )
    )
    db_session.commit()

    res = leave_service.resolve(
        db_session,
        agent,
        date(2026, 4, 10),
        worked_minutes=Decimal("0"),
        scheduled_minutes=Decimal("480"),
        requested_leave_type=LeaveType.PAID,
    )
    assert res.billing_status == BillingStatus.UNPAID_LWP
    assert res.unpaid_days == Decimal("1")
    assert res.leave_pay == Decimal("0")
    assert res.alerts


def test_manager_approval_policy_queues_pending(db_session):
    agent = _agent("MGR_APPROVAL_AGENT")
    db_session.add(agent)
    db_session.add(
        LeaveLedger(
            agent_id=agent.agent_id,
            leave_type=LeaveType.PAID,
            approved_balance=Decimal("0"),
            consumed_balance=Decimal("0"),
            overspend_policy=OverspendPolicy.MANAGER_APPROVAL,
            cycle_start=date(2026, 1, 1),
        )
    )
    db_session.commit()

    res = leave_service.resolve(
        db_session,
        agent,
        date(2026, 4, 10),
        worked_minutes=Decimal("0"),
        scheduled_minutes=Decimal("480"),
        requested_leave_type=LeaveType.PAID,
    )
    db_session.commit()
    assert res.billing_status == BillingStatus.PENDING_APPROVAL

    pending = db_session.query(PendingApproval).filter_by(agent_id=agent.agent_id).first()
    assert pending is not None
    assert pending.status == "PENDING"

    # Manager approves -> ledger should reflect 1 day consumed
    leave_service.decide_pending(db_session, pending, "APPROVE", "MGR_001")
    db_session.commit()
    ledger = db_session.query(LeaveLedger).filter_by(agent_id=agent.agent_id).first()
    assert ledger.consumed_balance == Decimal("1")
    assert pending.status == "APPROVED"


def test_worked_day_is_not_absence(db_session):
    agent = _agent("WORKED_AGENT")
    db_session.add(agent)
    db_session.commit()
    res = leave_service.resolve(
        db_session,
        agent,
        date(2026, 4, 10),
        worked_minutes=Decimal("480"),
        scheduled_minutes=Decimal("480"),
    )
    assert res.is_absence_day is False
    assert res.billing_status == BillingStatus.FINALIZED
