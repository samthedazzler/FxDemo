"""
Task 1 — Daily Productive Hours Calculation per Agent
======================================================
Reference: operations_task_1.pdf §1, operations_task_2.pdf §1 (Leave Approval Logic)

Formula
-------
  Productive Hours = sum(time_in_interval_m where Status Group == 'OCC') / 60

  Where OCC statuses = chat | after_contact_work | email | email_backlog
  (all transaction-handling time)

This is the single most important number Operations owns:
  - Finance uses it as "billable hours" for billing compliance and penalty risk.
  - WFM uses it to understand actual capacity delivered.

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv
  Available dates: 2026-04-12, 2026-04-13, 2026-04-14

Endpoint
--------
  GET /api/operations/productive-hours
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


# ── Response schemas ──────────────────────────────────────────────────────────

class AgentProductiveHours(BaseModel):
    agent_id: str
    work_date: date
    team: str
    site: str
    occ_minutes: float
    productive_hours: float
    present_hours: float
    productivity_pct: Optional[float]
    """Productivity % = Productive Hours / Present (Paid) Hours × 100
    Formula from ops_task_2.pdf §3 — Underperformance Detection."""
    status: str
    """'BELOW_THRESHOLD' if productivity_pct < 85%, else 'OK'."""


class ProductiveHoursSummary(BaseModel):
    query_date: date
    total_agents: int
    team_total_productive_hours: float
    team_avg_productive_hours: float
    team_avg_productivity_pct: Optional[float]
    agents: List[AgentProductiveHours]
    available_dates: List[date]


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get(
    "/productive-hours",
    response_model=ProductiveHoursSummary,
    summary="Task 1 — Daily Productive Hours per Agent",
    description=(
        "Calculates actual productive (OCC) hours per agent per day from the "
        "WFM activity CSV. Productive Hours = sum of time in OCC-group statuses "
        "(chat, after_contact_work, email). Also computes Productivity % = "
        "Productive Hours / Present Hours × 100 and flags agents below 85% threshold."
    ),
)
def get_productive_hours(
    query_date: date = Query(
        ...,
        description="Work date to analyse (YYYY-MM-DD). Available: 2026-04-12 to 2026-04-14.",
        example="2026-04-12",
    ),
    agent_id: Optional[str] = Query(None, description="Filter to a single agent ID."),
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

    agents_out: List[AgentProductiveHours] = []
    for rec in sorted(agg.values(), key=lambda r: r.agent_id):
        prod_pct = rec.productivity_pct
        agents_out.append(
            AgentProductiveHours(
                agent_id=rec.agent_id,
                work_date=rec.work_date,
                team=rec.team,
                site=rec.site,
                occ_minutes=round(rec.occ_minutes, 2),
                productive_hours=round(rec.productive_hours, 3),
                present_hours=round(rec.present_hours, 3),
                productivity_pct=prod_pct,
                status="BELOW_THRESHOLD" if (prod_pct is not None and prod_pct < 85.0) else "OK",
            )
        )

    total_prod_hrs = sum(a.productive_hours for a in agents_out)
    avg_prod_hrs = total_prod_hrs / len(agents_out) if agents_out else 0.0
    valid_pcts = [a.productivity_pct for a in agents_out if a.productivity_pct is not None]
    avg_prod_pct = round(sum(valid_pcts) / len(valid_pcts), 2) if valid_pcts else None

    return ProductiveHoursSummary(
        query_date=query_date,
        total_agents=len(agents_out),
        team_total_productive_hours=round(total_prod_hrs, 3),
        team_avg_productive_hours=round(avg_prod_hrs, 3),
        team_avg_productivity_pct=avg_prod_pct,
        agents=agents_out,
        available_dates=available_dates(),
    )
