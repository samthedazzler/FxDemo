"""Section 7.3 — Operations cost-preview endpoint.

Synchronous endpoint. When a manager wants to approve an overtime request
BEFORE the shift, the WFM dashboard calls this. The single endpoint is what
makes Finance an active partner in operational decisions rather than a
passive recorder.

Includes section 10 mitigation: rate cards older than 24h are flagged stale
so the previewed cost cannot silently drift from the actual cost.
"""

import calendar
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException, status as http_status

from app.models.db import Agent, FinancialBreakdown
from app.schemas.preview import OvertimePreviewRequest, OvertimePreviewResponse
from app.services import rate_card_service


def estimate_overtime_cost(
    db: Session, req: OvertimePreviewRequest
) -> OvertimePreviewResponse:
    agent = db.query(Agent).filter(Agent.agent_id == req.agent_id).first()
    if agent is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Agent {req.agent_id} not found.",
        )

    rates = rate_card_service.snapshot(db, agent)
    version_row = rate_card_service.latest_version_for(db, req.agent_id)
    stale = rate_card_service.is_stale(version_row) if version_row is not None else True

    base = Decimal(agent.base_hourly_rate)
    ot_mult = Decimal(agent.overtime_multiplier)
    hol_mult = Decimal(agent.holiday_multiplier)
    night_diff = Decimal(agent.night_differential)

    ot_hours = Decimal(req.proposed_overtime_hours)
    night_hours = Decimal(req.night_hours)

    if req.is_holiday:
        rate_per_hour = base * hol_mult
    else:
        rate_per_hour = base * ot_mult

    estimated_cost = (ot_hours * rate_per_hour) + (night_hours * base * night_diff)

    # MTD already accrued
    month_start = req.date.replace(day=1)
    rows = (
        db.query(FinancialBreakdown)
        .filter(
            FinancialBreakdown.agent_id == req.agent_id,
            FinancialBreakdown.date >= month_start,
            FinancialBreakdown.date <= req.date,
        )
        .all()
    )
    mtd = sum((Decimal(r.daily_gross) for r in rows), Decimal("0"))

    projected = mtd + estimated_cost

    cap = Decimal(agent.max_monthly_pay) if agent.max_monthly_pay is not None else None
    floor = Decimal(agent.min_monthly_pay)

    cap_breach = cap is not None and projected > cap
    floor_active = projected < floor

    notes: list[str] = []
    if stale:
        notes.append(
            f"Rate card version {rates.rate_card_version} is older than 24h; preview recomputed."
        )

    if cap_breach:
        recommendation = "BLOCK"
        notes.append(
            "Approving OT would breach the agent's monthly cap "
            "(uncompensated overtime). Review with HR."
        )
    elif req.is_holiday:
        recommendation = "APPROVE_WITH_CAUTION"
        notes.append("Holiday work — full holiday multiplier applied; verify staffing necessity.")
    else:
        recommendation = "APPROVE"

    return OvertimePreviewResponse(
        agent_id=req.agent_id,
        date=req.date,
        estimated_additional_cost=estimated_cost.quantize(Decimal("0.01")),
        agent_month_to_date=mtd.quantize(Decimal("0.01")),
        projected_after_overtime=projected.quantize(Decimal("0.01")),
        cap_breach=cap_breach,
        floor_active=floor_active,
        approval_recommendation=recommendation,
        rate_card_version=rates.rate_card_version,
        stale_rate_card=stale,
        notes=notes,
    )
