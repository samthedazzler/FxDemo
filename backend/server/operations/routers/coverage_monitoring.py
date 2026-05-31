"""
Task 7 — Coverage Monitoring (Active Agents vs Required per 30-Min Interval)
=============================================================================
Reference: operations_task_1.pdf §7, operations_task_2.pdf §10
           (Interval-Level Compliance — 30-Minute WFM Monitoring)

Formulas
--------
  Interval Compliance % = (Actual Productive Staff / Required Staff) × 100
  (ops_task_2.pdf §10)

  Example from doc:
    Required Staff = 80, Actual Productive Staff = 50
    Interval Compliance % = (50/80) × 100 = 62.5%
    → Operations must immediately rebalance staff.

  SLA threshold context (ops_task_1.pdf §7):
    "The 95% SLA threshold means on a 20-agent team, max 1 can be unavailable."
    → At any 30-min interval, active agents / total team >= 95%

  Active agents = agents with any OCC or CFT status record in that interval
  (counted as unique agents, not summed minutes)

  NOTE: Required staff per interval is NOT in the CSV — it comes from the
  WFM Capacity Planner / Schedule Builder. Without it, we can only report
  actual active agent counts. See DATA_REQUIREMENTS.md for full spec.

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv  (interval-level status records)

Endpoint
--------
  GET /api/operations/coverage-monitoring
"""

from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from operations.services.csv_loader import (
    build_interval_aggregates,
    available_dates,
    get_rows,
)

router = APIRouter()

SLA_THRESHOLD_PCT = 95.0
DEFAULT_TEAM_SIZE = 20  # assumed from ops_task_1.pdf §7 mention of "20-agent team"


class IntervalCoverage(BaseModel):
    interval_start: datetime
    interval_start_str: str
    active_agents: int
    """Unique agents with OCC or CFT record in this interval."""
    occ_agents: int
    """Unique agents in productive (OCC) state."""
    cft_agents: int
    """Unique agents in available/idle (CFT) state."""
    occ_minutes_total: float
    cft_minutes_total: float
    required_staff: Optional[int]
    """From WFM Schedule — NOT AVAILABLE in current CSV. Set via query param."""
    interval_compliance_pct: Optional[float]
    """(Actual OCC Staff / Required Staff) × 100 — only computable if required_staff provided."""
    coverage_gap: Optional[int]
    """max(0, Required Staff − Active Agents). Only if required_staff provided."""
    status: str
    """SUFFICIENT | UNDERSTAFFED | UNKNOWN (no required_staff)."""


class CoverageMonitoringSummary(BaseModel):
    query_date: date
    total_intervals: int
    peak_active_agents: int
    min_active_agents: int
    team_size_reference: int
    intervals_understaffed: int
    data_limitation: str
    intervals: List[IntervalCoverage]
    available_dates: List[date]


@router.get(
    "/coverage-monitoring",
    response_model=CoverageMonitoringSummary,
    summary="Task 7 — Interval-Level Coverage Monitoring (30-min)",
    description=(
        "Shows active agent count per 30-min interval for the requested date. "
        "Computes Interval Compliance % if required_staff is provided. "
        "Without required_staff from WFM, reports active counts only. "
        "Source: ops_task_2.pdf §10 formula."
    ),
)
def get_coverage_monitoring(
    query_date: date = Query(..., description="Work date (YYYY-MM-DD).", example="2026-04-12"),
    required_staff: Optional[int] = Query(
        None,
        description=(
            "Expected required staff per interval from WFM Capacity Planner. "
            "If omitted, interval compliance % cannot be computed."
        ),
    ),
):
    rows = get_rows()
    interval_agg = build_interval_aggregates(rows, filter_date=query_date)

    day_intervals = {
        iv: rec
        for (d, iv), rec in interval_agg.items()
        if d == query_date
    }

    if not day_intervals:
        dates = available_dates()
        raise HTTPException(
            status_code=404,
            detail={"message": f"No data for {query_date}.", "available_dates": [str(d) for d in dates]},
        )

    intervals_out: List[IntervalCoverage] = []
    for iv_start in sorted(day_intervals.keys()):
        rec = day_intervals[iv_start]
        compliance_pct = None
        gap = None
        status = "UNKNOWN"

        if required_staff is not None and required_staff > 0:
            compliance_pct = round(rec.occ_agents / required_staff * 100, 2)
            gap = max(0, required_staff - rec.active_agents)
            status = "UNDERSTAFFED" if gap > 0 else "SUFFICIENT"

        intervals_out.append(IntervalCoverage(
            interval_start=iv_start,
            interval_start_str=iv_start.strftime("%H:%M"),
            active_agents=rec.active_agents,
            occ_agents=rec.occ_agents,
            cft_agents=rec.cft_agents,
            occ_minutes_total=round(rec.occ_minutes, 2),
            cft_minutes_total=round(rec.cft_minutes, 2),
            required_staff=required_staff,
            interval_compliance_pct=compliance_pct,
            coverage_gap=gap,
            status=status,
        ))

    active_counts = [iv.active_agents for iv in intervals_out]
    understaffed = sum(1 for iv in intervals_out if iv.status == "UNDERSTAFFED")

    return CoverageMonitoringSummary(
        query_date=query_date,
        total_intervals=len(intervals_out),
        peak_active_agents=max(active_counts) if active_counts else 0,
        min_active_agents=min(active_counts) if active_counts else 0,
        team_size_reference=DEFAULT_TEAM_SIZE,
        intervals_understaffed=understaffed,
        data_limitation=(
            "required_staff per interval is NOT in the CSV. "
            "Provide it via ?required_staff=N for compliance % calculation. "
            "Source: WFM Capacity Planner / Schedule Builder."
        ),
        intervals=intervals_out,
        available_dates=available_dates(),
    )
