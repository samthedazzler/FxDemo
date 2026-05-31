"""Section 6 — Leave Consumption (the critical edge case).

Implements the three explicit policies set per agent at contract time:
  6.1 BLOCK            — reject; absence cannot be processed without HR override
  6.2 UNPAID_AUTO      — record as LWP, generate alert, day still counts for compliance
  6.3 MANAGER_APPROVAL — held pending; reconciliation prevents month-close while open
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.db import Agent, LeaveLedger, PendingApproval
from app.models.enums import BillingStatus, LeaveType, OverspendPolicy
from finance_func.app.services.billing_engine import LeaveResolution


HOURS_PER_DAY = Decimal("8")  # nominal pay day for leave valuation


def _pay_day_value(agent: Agent) -> Decimal:
    """One leave-day pays at base_hourly_rate * (weekly_contracted_hours / 5)."""
    daily_hours = Decimal(agent.weekly_contracted_hours) / Decimal(5)
    if daily_hours == 0:
        daily_hours = HOURS_PER_DAY
    return Decimal(agent.base_hourly_rate) * daily_hours


def is_absence_day(worked_minutes: Decimal, scheduled_minutes: Decimal) -> bool:
    return worked_minutes == 0 and scheduled_minutes > 0


def _select_ledger(
    db: Session, agent_id: str, preferred_type: Optional[LeaveType] = None
) -> Optional[LeaveLedger]:
    """Find a leave ledger entry to decrement against.

    If a preferred leave_type is provided, use that. Otherwise use any ledger
    with remaining balance > 0, preferring PAID then SICK then COMP_OFF.
    """
    query = db.query(LeaveLedger).filter(LeaveLedger.agent_id == agent_id)
    if preferred_type is not None:
        return query.filter(LeaveLedger.leave_type == preferred_type).first()

    ledgers = query.all()
    preference = [LeaveType.PAID, LeaveType.SICK, LeaveType.COMP_OFF, LeaveType.BEREAVEMENT]
    for lt in preference:
        for ledger in ledgers:
            if ledger.leave_type == lt and ledger.remaining_balance > 0:
                return ledger
    return ledgers[0] if ledgers else None


def resolve(
    db: Session,
    agent: Agent,
    work_date: date,
    worked_minutes: Decimal,
    scheduled_minutes: Decimal,
    requested_leave_type: Optional[LeaveType] = None,
) -> LeaveResolution:
    """Section 5.1 Step 2 — Resolve leave consumption.

    Called only when (worked_minutes == 0 and scheduled_minutes > 0).
    """
    res = LeaveResolution()

    if not is_absence_day(worked_minutes, scheduled_minutes):
        return res

    res.is_absence_day = True
    pay_day_value = _pay_day_value(agent)

    ledger = _select_ledger(db, agent.agent_id, requested_leave_type)

    if ledger is None:
        # No ledger entry at all — treat as UNPAID and alert.
        res.policy_applied = OverspendPolicy.UNPAID_AUTO
        res.billing_status = BillingStatus.UNPAID_LWP
        res.unpaid_days = Decimal("1")
        res.leave_pay = Decimal("0")
        res.alerts.append(
            f"No leave ledger for agent {agent.agent_id}; absence on {work_date} recorded as LWP."
        )
        return res

    res.leave_type_used = ledger.leave_type.value

    # Capacity check (1 leave-day per absence day)
    if ledger.remaining_balance >= 1:
        ledger.consumed_balance = Decimal(ledger.consumed_balance) + Decimal("1")
        db.add(ledger)
        res.paid_from_balance_days = Decimal("1")
        res.leave_pay = pay_day_value
        res.billing_status = BillingStatus.FINALIZED
        return res

    # Overspend — apply the three policies
    res.policy_applied = ledger.overspend_policy

    if ledger.overspend_policy == OverspendPolicy.BLOCK:
        # 6.1 BLOCK — return error. Caller surfaces 409.
        res.billing_status = BillingStatus.BLOCKED
        res.blocked_reason = (
            f"BLOCK policy: leave balance exhausted for agent {agent.agent_id} "
            f"on {work_date}. HR override required."
        )
        res.alerts.append(res.blocked_reason)
        return res

    if ledger.overspend_policy == OverspendPolicy.UNPAID_AUTO:
        # 6.2 UNPAID_AUTO — record at zero rate, day still counts, HR alert.
        res.billing_status = BillingStatus.UNPAID_LWP
        res.unpaid_days = Decimal("1")
        res.leave_pay = Decimal("0")
        res.alerts.append(
            f"UNPAID_AUTO: agent {agent.agent_id} absent on {work_date} with zero balance; "
            "recorded as LWP. Daily HR alert raised."
        )
        return res

    if ledger.overspend_policy == OverspendPolicy.MANAGER_APPROVAL:
        # 6.3 MANAGER_APPROVAL — queue and do NOT finalize.
        existing = (
            db.query(PendingApproval)
            .filter(PendingApproval.agent_id == agent.agent_id, PendingApproval.date == work_date)
            .first()
        )
        if existing is None:
            db.add(
                PendingApproval(
                    agent_id=agent.agent_id,
                    date=work_date,
                    leave_type=ledger.leave_type,
                    reason="Leave balance exhausted; manager approval required.",
                    status="PENDING",
                )
            )
        res.billing_status = BillingStatus.PENDING_APPROVAL
        res.leave_pay = Decimal("0")
        res.alerts.append(
            f"MANAGER_APPROVAL: absence on {work_date} for agent {agent.agent_id} queued for "
            "manager review. Billing held pending decision."
        )
        return res

    # Defensive fallback
    res.billing_status = BillingStatus.UNPAID_LWP
    res.unpaid_days = Decimal("1")
    return res


def decide_pending(
    db: Session,
    pending: PendingApproval,
    decision: str,
    manager_id: str,
) -> PendingApproval:
    """Section 6.3 — apply manager decision. APPROVE => treat as paid exception.
    DENY => revert to unpaid."""
    from datetime import datetime

    if decision == "APPROVE":
        pending.status = "APPROVED"
        # Increase approved_balance so the day can decrement cleanly.
        ledger = (
            db.query(LeaveLedger)
            .filter(
                LeaveLedger.agent_id == pending.agent_id,
                LeaveLedger.leave_type == pending.leave_type,
            )
            .first()
        )
        if ledger is not None:
            ledger.approved_balance = Decimal(ledger.approved_balance) + Decimal("1")
            ledger.consumed_balance = Decimal(ledger.consumed_balance) + Decimal("1")
            db.add(ledger)
    elif decision == "DENY":
        pending.status = "DENIED"
    pending.manager_id = manager_id
    pending.decided_at = datetime.utcnow()
    db.add(pending)
    return pending
