"""
Task 2 — Shrinkage Rate Monitoring
====================================
Reference: operations_task_1.pdf §2, BEST WFM §1.4 / §2.2

IMPORTANT — Formula Correction Note
-------------------------------------
operations_task_1.pdf §2 explicitly states:
  "NOT THE CORRECT FORMULA AND MEANING HERE AS WE DISCUSSED"
  regarding the simple (Break + Lunch) ÷ Total logged minutes formula.

Correct formula per BEST WFM Reference Document §1.4:

  In-Office Shrinkage Rate = In-Office Shrinkage Minutes / Present Hours × 100

  Where:
    In-Office Shrinkage = Break + Lunch + Training + Meeting minutes
    Present Hours (excl. NHT) = Production Hours + In-Office Shrinkage
    Production Hours = Transaction (OCC) + Available (CFT) hours

  Optimal target for an 8-hour shift ≈ 10.4%
    (50 min break+lunch out of ~480 min present time)

This helps:
  - Finance understand cost leakage
  - WFM calibrate seat calculations:
    Required Seats = Base FTEs ÷ (1 − Shrinkage %)

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv  (break, lunch statuses via NaN Status Group)

Endpoint
--------
  GET /api/operations/shrinkage-rate
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from operations.services.csv_loader import (
    build_agent_day_aggregates,
    available_dates,
    get_rows,
)

router = APIRouter()

# Optimal shrinkage for an 8-hour shift: 50 min / 480 min = ~10.4%
OPTIMAL_SHRINKAGE_PCT = 10.4
SHRINKAGE_UPPER_THRESHOLD = 20.0   # flag if > 20%


class AgentShrinkage(BaseModel):
    agent_id: str
    work_date: date
    team: str
    break_minutes: float
    training_minutes: float
    in_office_shrinkage_minutes: float
    present_minutes: float
    in_office_shrinkage_rate_pct: Optional[float]
    """In-Office Shrinkage Rate = Shrinkage Minutes / Present Minutes × 100
    (BEST WFM §1.4 — NOT the simple Break/Total formula)."""
    status: str
    """'HIGH' if > 20%, 'LOW_BREAK' if < 5% (break compliance risk), else 'OK'."""


class ShrinkageSummary(BaseModel):
    query_date: date
    total_agents: int
    team_avg_shrinkage_rate_pct: Optional[float]
    optimal_target_pct: float
    required_seats_factor: Optional[float]
    """WFM staffing factor = 1 / (1 − shrinkage_rate). Use: Required Seats = Base FTEs × factor."""
    agents: List[AgentShrinkage]
    available_dates: List[date]


@router.get(
    "/shrinkage-rate",
    response_model=ShrinkageSummary,
    summary="Task 2 — In-Office Shrinkage Rate per Agent",
    description=(
        "Calculates In-Office Shrinkage Rate per BEST WFM §1.4. "
        "Formula: Shrinkage Minutes / Present Minutes × 100. "
        "This is NOT the simple Break+Lunch/Total formula — see task description."
    ),
)
def get_shrinkage_rate(
    query_date: date = Query(..., description="Work date (YYYY-MM-DD).", example="2026-04-12"),
    agent_id: Optional[str] = Query(None, description="Filter to a single agent."),
):
    rows = get_rows()
    agg = build_agent_day_aggregates(rows, filter_date=query_date, filter_agent=agent_id)

    if not agg:
        dates = available_dates()
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"No data found for date {query_date}.",
                "available_dates": [str(d) for d in dates],
            },
        )

    agents_out: List[AgentShrinkage] = []
    for rec in sorted(agg.values(), key=lambda r: r.agent_id):
        shrink_pct = rec.in_office_shrinkage_rate_pct

        if shrink_pct is None:
            status = "NO_DATA"
        elif shrink_pct > SHRINKAGE_UPPER_THRESHOLD:
            status = "HIGH"
        elif shrink_pct < 5.0:
            status = "LOW_BREAK"
        else:
            status = "OK"

        agents_out.append(
            AgentShrinkage(
                agent_id=rec.agent_id,
                work_date=rec.work_date,
                team=rec.team,
                break_minutes=round(rec.break_minutes, 2),
                training_minutes=round(rec.training_minutes, 2),
                in_office_shrinkage_minutes=round(rec.in_office_shrinkage_minutes, 2),
                present_minutes=round(rec.present_minutes, 2),
                in_office_shrinkage_rate_pct=shrink_pct,
                status=status,
            )
        )

    valid_pcts = [a.in_office_shrinkage_rate_pct for a in agents_out if a.in_office_shrinkage_rate_pct is not None]
    avg_shrink = round(sum(valid_pcts) / len(valid_pcts), 2) if valid_pcts else None
    seats_factor = round(1 / (1 - avg_shrink / 100), 4) if (avg_shrink is not None and avg_shrink < 100) else None

    return ShrinkageSummary(
        query_date=query_date,
        total_agents=len(agents_out),
        team_avg_shrinkage_rate_pct=avg_shrink,
        optimal_target_pct=OPTIMAL_SHRINKAGE_PCT,
        required_seats_factor=seats_factor,
        agents=agents_out,
        available_dates=available_dates(),
    )
