"""Section 7 — The WFM <-> Finance Contract.

  7.1 POST /finance/breakdown   (WFM publishes; Finance returns cost preview)
  7.2 Response shape with components + month_to_date + projected_monthly_gross
  7.3 POST /finance/preview     (synchronous OT cost preview)

Also exposes read endpoints used by the Java frontend dashboards:
  GET  /finance/breakdown/{agent_id}/{date}
  GET  /finance/breakdown/{agent_id}             (range query)
  GET  /finance/monthly/{agent_id}/{year}/{month}
"""

from datetime import date as ddate
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import FinancialBreakdown
from app.models.enums import LeaveType
from app.schemas.breakdown import HourlyBreakdownIn, WFMRawAggregateRequest
from app.schemas.financial import BillingResponse, FinancialBreakdownOut, MonthlyRollup
from app.schemas.preview import OvertimePreviewRequest, OvertimePreviewResponse
from app.services import wfm_aggregator
from finance_func.app.services import finance_service, preview_service

router = APIRouter(prefix="/finance", tags=["Finance"])


@router.post("/breakdown", response_model=BillingResponse)
def post_breakdown(
    payload: HourlyBreakdownIn,
    requested_leave_type: Optional[LeaveType] = Query(
        None, description="Optional: pin which leave type to decrement on absence."
    ),
    db: Session = Depends(get_db),
):
    """Section 7.1 — WFM publishes daily-finalized event per agent at
    end-of-shift. Finance returns the cost preview (section 7.2)."""
    _, response = finance_service.process_breakdown(db, payload, requested_leave_type)
    return response


@router.post("/breakdown/from-wfm-raw", response_model=BillingResponse)
def post_breakdown_from_raw(
    payload: WFMRawAggregateRequest,
    requested_leave_type: Optional[LeaveType] = Query(None),
    db: Session = Depends(get_db),
):
    """Convenience endpoint — accepts the WFM Aggregator's raw {status -> minutes}
    map (section 11) and routes it through the same pipeline."""
    hb = wfm_aggregator.aggregate_status_map(
        agent_id=payload.agent_id,
        work_date=payload.date,
        status_minutes=payload.status_minutes,
        scheduled_minutes=payload.scheduled_minutes,
        is_holiday=payload.is_holiday,
        night_minutes=payload.night_minutes,
        site=payload.site,
    )
    _, response = finance_service.process_breakdown(db, hb, requested_leave_type)
    return response


@router.post("/preview", response_model=OvertimePreviewResponse)
def post_preview(payload: OvertimePreviewRequest, db: Session = Depends(get_db)):
    """Section 7.3 — Operations cost-preview endpoint.

    Synchronous. Called by the WFM dashboard before a manager approves an
    overtime request. Returns estimated additional cost, projected MTD, cap
    breach flag, and an approval recommendation."""
    return preview_service.estimate_overtime_cost(db, payload)


@router.get("/breakdown/{agent_id}/{work_date}", response_model=FinancialBreakdownOut)
def get_breakdown(agent_id: str, work_date: ddate, db: Session = Depends(get_db)):
    fb = (
        db.query(FinancialBreakdown)
        .filter(FinancialBreakdown.agent_id == agent_id, FinancialBreakdown.date == work_date)
        .order_by(FinancialBreakdown.created_at.desc())
        .first()
    )
    if fb is None:
        raise HTTPException(status_code=404, detail="No financial breakdown for that agent/date.")
    return _fb_to_out(fb)


@router.get("/breakdown/{agent_id}", response_model=List[FinancialBreakdownOut])
def list_breakdowns(
    agent_id: str,
    start: Optional[ddate] = None,
    end: Optional[ddate] = None,
    db: Session = Depends(get_db),
):
    q = db.query(FinancialBreakdown).filter(FinancialBreakdown.agent_id == agent_id)
    if start is not None:
        q = q.filter(FinancialBreakdown.date >= start)
    if end is not None:
        q = q.filter(FinancialBreakdown.date <= end)
    return [_fb_to_out(r) for r in q.order_by(FinancialBreakdown.date.asc()).all()]


@router.get("/monthly/{agent_id}/{year}/{month}", response_model=MonthlyRollup)
def monthly_rollup(agent_id: str, year: int, month: int, db: Session = Depends(get_db)):
    """Section 5.1 step 5 + step 6 — month-close rollup."""
    return finance_service.monthly_rollup(db, agent_id, year, month)


def _fb_to_out(r: FinancialBreakdown) -> FinancialBreakdownOut:
    from app.schemas.financial import PayComponents

    return FinancialBreakdownOut(
        id=r.id,
        agent_id=r.agent_id,
        date=r.date,
        daily_gross=r.daily_gross,
        components=PayComponents(
            regular_pay=r.regular_pay,
            overtime_pay=r.overtime_pay,
            holiday_pay=r.holiday_pay,
            night_premium=r.night_premium,
            leave_pay=r.leave_pay,
        ),
        month_to_date_gross=r.month_to_date_gross,
        projected_monthly_gross=r.projected_monthly_gross,
        monthly_pay=r.monthly_pay,
        min_max_status=r.min_max_status,
        delta_reason=r.delta_reason,
        billing_status=r.billing_status,
        currency=r.currency,
        content_hash=r.content_hash,
        parent_id=r.parent_id,
        rate_card_version=r.rate_card_version,
        provenance=r.provenance,
        alerts=r.alerts or [],
        created_at=r.created_at,
    )
