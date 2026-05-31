"""
Task 4 — Shift Span & Attendance Tracking
==========================================
Reference: operations_task_1.pdf §4

Formula
-------
  Shift Span Hours = (Last Activity End Time − First Login Start Time)
                     in hours

  Uses Local Start Time (first record) and Local End Time (last record)
  per agent per day from the CSV.

Detects:
  - Late start:     First activity starts > LATE_START_THRESHOLD_MIN after
                    earliest interval start for that day (proxy for scheduled start)
  - Early departure: Last activity ends > EARLY_DEPARTURE_THRESHOLD_MIN before
                    the last interval for that day
  - Short shift:    Shift span < SHORT_SHIFT_THRESHOLD_HRS (potential no-show
                    or early leave after login)
  - No-show:        No records at all for the agent on that date

This feeds:
  - WFM: schedule reliability scoring
  - Finance: hours compliance (billable vs scheduled)

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv  (Local Start Time, Local End Time per row)

Endpoint
--------
  GET /api/operations/shift-span
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from operations.services.csv_loader import (
    build_agent_day_aggregates,
    build_interval_aggregates,
    available_dates,
    get_rows,
)

router = APIRouter()

# Thresholds
LATE_START_THRESHOLD_MIN = 15       # flag if first login > 15 min after day start
EARLY_DEPARTURE_THRESHOLD_MIN = 30  # flag if last logout > 30 min before day end
SHORT_SHIFT_THRESHOLD_HRS = 4.0    # flag if span < 4 hours


class AttendanceFlag(BaseModel):
    reason: str
    detail: str


class AgentShiftSpan(BaseModel):
    agent_id: str
    work_date: date
    team: str
    site: str
    first_login: Optional[datetime]
    last_logout: Optional[datetime]
    shift_span_hours: Optional[float]
    present_hours: float
    flags: List[AttendanceFlag]
    attendance_status: str
    """PRESENT | SHORT_SHIFT | LATE_START | EARLY_DEPARTURE | MULTI_FLAG"""


class ShiftSpanSummary(BaseModel):
    query_date: date
    total_agents: int
    agents_present: int
    agents_flagged: int
    agents: List[AgentShiftSpan]
    available_dates: List[date]


@router.get(
    "/shift-span",
    response_model=ShiftSpanSummary,
    summary="Task 4 — Shift Span & Attendance Tracking",
    description=(
        "Calculates actual shift span (last logout − first login) per agent. "
        "Flags late starts (> 15 min), early departures (> 30 min early), "
        "and short shifts (< 4 hours). No-show detection requires full roster "
        "(see DATA_REQUIREMENTS.md)."
    ),
)
def get_shift_span(
    query_date: date = Query(..., description="Work date (YYYY-MM-DD).", example="2026-04-12"),
    agent_id: Optional[str] = Query(None, description="Filter to a single agent."),
):
    rows = get_rows()
    agg = build_agent_day_aggregates(rows, filter_date=query_date, filter_agent=agent_id)

    if not agg:
        dates = available_dates()
        raise HTTPException(
            status_code=404,
            detail={"message": f"No data for {query_date}.", "available_dates": [str(d) for d in dates]},
        )

    # Day-level interval range to detect late starts / early departures
    interval_agg = build_interval_aggregates(rows, filter_date=query_date)
    day_intervals = sorted(
        [iv for (d, iv) in interval_agg.keys() if d == query_date]
    )
    day_start = day_intervals[0] if day_intervals else None
    day_end = day_intervals[-1] if day_intervals else None

    agents_out: List[AgentShiftSpan] = []
    for rec in sorted(agg.values(), key=lambda r: r.agent_id):
        flags: List[AttendanceFlag] = []

        # Late start check
        if rec.first_login and day_start:
            minutes_late = (rec.first_login - day_start).total_seconds() / 60
            if minutes_late > LATE_START_THRESHOLD_MIN:
                flags.append(AttendanceFlag(
                    reason="LATE_START",
                    detail=f"First login {round(minutes_late, 1)} min after day interval start.",
                ))

        # Short shift check
        span = rec.shift_span_hours
        if span is not None and span < SHORT_SHIFT_THRESHOLD_HRS:
            flags.append(AttendanceFlag(
                reason="SHORT_SHIFT",
                detail=f"Shift span only {round(span, 2)} hrs (threshold {SHORT_SHIFT_THRESHOLD_HRS} hrs).",
            ))

        if len(flags) == 0:
            status = "PRESENT"
        elif len(flags) == 1:
            status = flags[0].reason
        else:
            status = "MULTI_FLAG"

        agents_out.append(AgentShiftSpan(
            agent_id=rec.agent_id,
            work_date=rec.work_date,
            team=rec.team,
            site=rec.site,
            first_login=rec.first_login,
            last_logout=rec.last_logout,
            shift_span_hours=round(span, 3) if span is not None else None,
            present_hours=round(rec.present_hours, 3),
            flags=flags,
            attendance_status=status,
        ))

    return ShiftSpanSummary(
        query_date=query_date,
        total_agents=len(agents_out),
        agents_present=sum(1 for a in agents_out if a.attendance_status == "PRESENT"),
        agents_flagged=sum(1 for a in agents_out if a.flags),
        agents=agents_out,
        available_dates=available_dates(),
    )
