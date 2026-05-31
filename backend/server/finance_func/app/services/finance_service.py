"""Orchestrator that wires the deterministic data flow (section 3.2):

    WFM hourly breakdown --> Leave Ledger lookup --> Rate Card lookup
                         --> Billing Engine --> Per-agent financial record

This is the single entry point used by the /finance/breakdown router. It is
the only place that touches multiple repositories at once; the Billing
Engine itself stays pure.
"""

import calendar
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status as http_status

from app.models.db import (
    Agent,
    FinancialBreakdown,
    HourlyBreakdown,
    HolidayCalendar,
)
from app.models.enums import BillingStatus, LeaveType
from app.schemas.breakdown import HourlyBreakdownIn
from app.schemas.financial import BillingResponse, PayComponents
from app.services import audit, leave_service, rate_card_service
from finance_func.app.services import billing_engine
from finance_func.app.services.billing_engine import HourlyInputs, BillingResult
from app.utils.hashing import content_hash


def _hours_input_from_schema(payload: HourlyBreakdownIn) -> HourlyInputs:
    return HourlyInputs(
        agent_id=payload.agent_id,
        date=payload.date,
        productive_minutes=Decimal(payload.productive_minutes),
        available_minutes=Decimal(payload.available_minutes),
        break_minutes=Decimal(payload.break_minutes),
        training_minutes=Decimal(payload.training_minutes),
        scheduled_minutes=Decimal(payload.scheduled_minutes),
        worked_minutes=Decimal(payload.worked_minutes),
        overtime_minutes=Decimal(payload.overtime_minutes),
        is_holiday=payload.is_holiday,
        night_minutes=Decimal(payload.night_minutes),
    )


def _month_to_date_gross(db: Session, agent_id: str, ref: date) -> Decimal:
    month_start = ref.replace(day=1)
    rows = (
        db.query(FinancialBreakdown)
        .filter(
            FinancialBreakdown.agent_id == agent_id,
            FinancialBreakdown.date >= month_start,
            FinancialBreakdown.date < ref,
        )
        .all()
    )
    return sum((Decimal(r.daily_gross) for r in rows), Decimal("0"))


def _resolve_holiday(db: Session, payload: HourlyBreakdownIn, agent: Agent) -> bool:
    """Section 10 — Holiday calendar is per-site, not global."""
    if payload.is_holiday:
        return True
    site = payload.site or agent.primary_site
    if site is None:
        return False
    row = (
        db.query(HolidayCalendar)
        .filter(HolidayCalendar.site == site, HolidayCalendar.date == payload.date)
        .first()
    )
    return row is not None


def process_breakdown(
    db: Session,
    payload: HourlyBreakdownIn,
    requested_leave_type: Optional[LeaveType] = None,
) -> tuple[FinancialBreakdown, BillingResponse]:
    """Section 7.1 + 7.2 — end-to-end processing of one daily breakdown."""

    agent = db.query(Agent).filter(Agent.agent_id == payload.agent_id).first()
    if agent is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Agent {payload.agent_id} not found in Agent Master.",
        )

    # Holiday resolution (per-site)
    payload.is_holiday = _resolve_holiday(db, payload, agent)

    # Persist (or update) the raw breakdown so WFM has audit visibility.
    existing_hb = (
        db.query(HourlyBreakdown)
        .filter(
            HourlyBreakdown.agent_id == payload.agent_id,
            HourlyBreakdown.date == payload.date,
        )
        .first()
    )
    parent_id: Optional[int] = None
    if existing_hb is None:
        existing_hb = HourlyBreakdown(
            agent_id=payload.agent_id,
            date=payload.date,
            productive_minutes=payload.productive_minutes,
            available_minutes=payload.available_minutes,
            break_minutes=payload.break_minutes,
            training_minutes=payload.training_minutes,
            scheduled_minutes=payload.scheduled_minutes,
            worked_minutes=payload.worked_minutes,
            overtime_minutes=payload.overtime_minutes,
            is_holiday=payload.is_holiday,
            night_minutes=payload.night_minutes,
            source_status_breakdown=payload.source_status_breakdown,
            site=payload.site,
        )
        db.add(existing_hb)
    else:
        # Corrections create a new financial record; the original is preserved.
        prior_fb = (
            db.query(FinancialBreakdown)
            .filter(
                FinancialBreakdown.agent_id == payload.agent_id,
                FinancialBreakdown.date == payload.date,
            )
            .order_by(FinancialBreakdown.created_at.desc())
            .first()
        )
        if prior_fb is not None:
            parent_id = prior_fb.id
        existing_hb.productive_minutes = payload.productive_minutes
        existing_hb.available_minutes = payload.available_minutes
        existing_hb.break_minutes = payload.break_minutes
        existing_hb.training_minutes = payload.training_minutes
        existing_hb.scheduled_minutes = payload.scheduled_minutes
        existing_hb.worked_minutes = payload.worked_minutes
        existing_hb.overtime_minutes = payload.overtime_minutes
        existing_hb.is_holiday = payload.is_holiday
        existing_hb.night_minutes = payload.night_minutes
        existing_hb.source_status_breakdown = payload.source_status_breakdown
        existing_hb.site = payload.site
        db.add(existing_hb)

    # Step 2 — leave consumption
    leave_res = leave_service.resolve(
        db,
        agent,
        payload.date,
        Decimal(payload.worked_minutes),
        Decimal(payload.scheduled_minutes),
        requested_leave_type,
    )

    if leave_res.billing_status == BillingStatus.BLOCKED:
        # Section 6.1 BLOCK — return error; absence cannot be processed.
        audit.log_event(
            db,
            event_type="BILLING_BLOCKED",
            payload={
                "agent_id": payload.agent_id,
                "date": payload.date.isoformat(),
                "reason": leave_res.blocked_reason,
            },
            agent_id=payload.agent_id,
        )
        db.commit()
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": "BLOCK_POLICY_TRIGGERED",
                "message": leave_res.blocked_reason,
                "agent_id": payload.agent_id,
                "date": payload.date.isoformat(),
            },
        )

    # Step 3 + 4 + 5 + 6 — Billing Engine
    rates = rate_card_service.snapshot(db, agent)
    hours = _hours_input_from_schema(payload)

    mtd_before = _month_to_date_gross(db, payload.agent_id, payload.date)
    days_elapsed = payload.date.day
    days_in_month = calendar.monthrange(payload.date.year, payload.date.month)[1]

    result: BillingResult = billing_engine.compute(
        hours=hours,
        rates=rates,
        leave_resolution=leave_res,
        month_to_date_gross_before_today=mtd_before,
        days_elapsed_in_month=days_elapsed,
        days_in_month=days_in_month,
    )

    # Step 7 — persist with content hash (section 8)
    hash_payload = {**result.provenance, "components": result.components.model_dump(mode="json")}
    fb_hash = content_hash(hash_payload)

    fb = FinancialBreakdown(
        agent_id=result.agent_id,
        date=result.date,
        regular_pay=result.components.regular_pay,
        overtime_pay=result.components.overtime_pay,
        holiday_pay=result.components.holiday_pay,
        night_premium=result.components.night_premium,
        leave_pay=result.components.leave_pay,
        daily_gross=result.daily_gross,
        month_to_date_gross=result.month_to_date_gross,
        projected_monthly_gross=result.projected_monthly_gross,
        monthly_pay=result.monthly_pay,
        delta_reason=result.delta_reason,
        min_max_status=result.min_max_status,
        billing_status=result.billing_status,
        currency=result.currency,
        content_hash=fb_hash,
        parent_id=parent_id,
        rate_card_version=result.rate_card_version,
        provenance=_to_jsonable(result.provenance),
        alerts=result.alerts,
    )
    db.add(fb)
    db.flush()

    audit.log_event(
        db,
        event_type="BILLING_COMPUTED",
        payload={
            "agent_id": result.agent_id,
            "date": result.date.isoformat(),
            "daily_gross": str(result.daily_gross),
            "billing_status": result.billing_status.value,
            "rate_card_version": result.rate_card_version,
            "alerts": result.alerts,
        },
        agent_id=result.agent_id,
        target_id=str(fb.id),
        content_hash=fb_hash,
    )
    db.commit()
    db.refresh(fb)

    response = BillingResponse(
        agent_id=result.agent_id,
        date=result.date,
        daily_gross=result.daily_gross,
        components=result.components,
        month_to_date_gross=result.month_to_date_gross,
        projected_monthly_gross=result.projected_monthly_gross,
        min_max_status=result.min_max_status,
        delta_reason=result.delta_reason,
        billing_status=result.billing_status,
        alerts=result.alerts,
        content_hash=fb_hash,
        rate_card_version=result.rate_card_version,
    )
    return fb, response


def _to_jsonable(obj):
    from decimal import Decimal as D
    from datetime import date as _date, datetime as _dt

    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, D):
        return str(obj)
    if isinstance(obj, (_date, _dt)):
        return obj.isoformat()
    return obj


def monthly_rollup(db: Session, agent_id: str, year: int, month: int):
    """Section 5.1 step 5 — roll up daily_gross into a monthly window.

    Then re-apply min/max enforcement against the FINAL monthly_gross for
    binding payroll. This is the official month-close number.
    """
    from app.schemas.financial import MonthlyRollup

    days_in_month = calendar.monthrange(year, month)[1]
    start = date(year, month, 1)
    end = date(year, month, days_in_month)

    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agent_id} not found.",
        )

    rows = (
        db.query(FinancialBreakdown)
        .filter(
            FinancialBreakdown.agent_id == agent_id,
            FinancialBreakdown.date >= start,
            FinancialBreakdown.date <= end,
        )
        .all()
    )

    total = Decimal("0")
    comp = PayComponents(
        regular_pay=Decimal("0"),
        overtime_pay=Decimal("0"),
        holiday_pay=Decimal("0"),
        night_premium=Decimal("0"),
        leave_pay=Decimal("0"),
    )
    pending_count = 0
    for r in rows:
        if r.billing_status == BillingStatus.PENDING_APPROVAL:
            pending_count += 1
            continue
        total += Decimal(r.daily_gross)
        comp = PayComponents(
            regular_pay=comp.regular_pay + Decimal(r.regular_pay),
            overtime_pay=comp.overtime_pay + Decimal(r.overtime_pay),
            holiday_pay=comp.holiday_pay + Decimal(r.holiday_pay),
            night_premium=comp.night_premium + Decimal(r.night_premium),
            leave_pay=comp.leave_pay + Decimal(r.leave_pay),
        )

    monthly_pay, delta_reason, mm_status, mm_alerts = billing_engine.step6_apply_min_max(
        total,
        Decimal(agent.min_monthly_pay),
        Decimal(agent.max_monthly_pay) if agent.max_monthly_pay is not None else None,
    )

    alerts = list(mm_alerts)
    if pending_count > 0:
        # Section 6.3 — Reconciliation prevents month-close while pending exist.
        alerts.append(
            f"{pending_count} day(s) PENDING_APPROVAL. Month-close blocked until resolved."
        )

    return MonthlyRollup(
        agent_id=agent_id,
        year=year,
        month=month,
        monthly_gross=total,
        monthly_pay=monthly_pay,
        min_monthly_pay=Decimal(agent.min_monthly_pay),
        max_monthly_pay=(Decimal(agent.max_monthly_pay) if agent.max_monthly_pay else None),
        delta_reason=delta_reason,
        min_max_status=mm_status,
        days_counted=len(rows) - pending_count,
        breakdown_by_component=comp,
        alerts=alerts,
    )
