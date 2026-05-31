"""
Task 12 — Schedule Adherence % (Full Version)
==============================================
Reference: operations_task_1.pdf §12, operations_task_2.pdf §9

PURPOSE
-------
  Schedule Adherence measures whether agents worked when they were scheduled to work.
  This is distinct from Occupancy (how busy they were while working).

  Formula (ops_task_2.pdf §9):
    Schedule Adherence % = (Adherent Minutes / Scheduled Minutes) × 100

    Adherent Minutes = minutes the agent was in the correct status during their
                       scheduled working window (i.e., OCC or CFT while scheduled
                       to be "on phones"; on break while scheduled for break).

  Threshold (ops_task_2.pdf §9):
    Target >= 90% adherence
    < 85%: flag for supervisor review
    < 75%: escalate to manager

  Partial Adherence (current data only):
    The CSV provides actual OCC/CFT/shrinkage minutes and login/logout times.
    WITHOUT the scheduled start/end time per agent, we can only compute:
      - Whether the agent showed up (shift-span check — Task 4)
      - How many minutes they were productive
    We CANNOT compute adherence without the planned schedule to compare against.

DATA STATUS: LIMITED — see DATA_REQUIREMENTS.md
-------------------------------------------------
  REQUIRED but NOT in current CSV:
    - Scheduled start time per agent per day (from WFM Schedule Builder)
    - Scheduled end time per agent per day
    - Scheduled break windows (when agent is supposed to be on break)
    - Scheduled queue assignment per interval (for interval-level adherence)

  AVAILABLE in current CSV:
    - Actual first login time (first_login → shift_span start)
    - Actual last logout time (last_logout → shift_span end)
    - Actual OCC/CFT/break minutes per day
    - Interval-level status records (30-min resolution)

Endpoint
--------
  GET /api/operations/schedule-adherence  [LIMITED_DATA]
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

DATA_STATUS = "LIMITED_DATA"
ADHERENCE_TARGET_PCT = 90.0
ADHERENCE_SUPERVISOR_FLAG_PCT = 85.0
ADHERENCE_ESCALATE_PCT = 75.0


class PartialAdherenceAgent(BaseModel):
    agent_id: str
    work_date: date
    team: str
    actual_present_hours: float
    actual_occ_minutes: float
    actual_cft_minutes: float
    actual_break_minutes: float
    first_login: Optional[str]
    last_logout: Optional[str]
    shift_span_hours: Optional[float]
    scheduled_start: Optional[str]
    """NULL — not available in current CSV. Requires WFM Schedule Builder."""
    scheduled_end: Optional[str]
    """NULL — not available in current CSV. Requires WFM Schedule Builder."""
    scheduled_minutes: Optional[float]
    """NULL — cannot compute without scheduled start/end."""
    adherent_minutes: Optional[float]
    """NULL — cannot compute without scheduled start/end."""
    adherence_pct: Optional[float]
    """NULL — cannot compute without scheduled start/end."""
    adherence_status: str
    """INSUFFICIENT_DATA until schedule is loaded."""
    data_limitation: str


class ScheduleAdherenceSummary(BaseModel):
    query_date: date
    data_status: str
    total_agents: int
    agents_with_full_adherence_data: int
    target_adherence_pct: float
    supervisor_flag_threshold: float
    escalation_threshold: float
    agents: List[PartialAdherenceAgent]
    adherence_formula: str
    missing_data: List[str]
    available_dates: List[date]


@router.get(
    "/schedule-adherence",
    response_model=ScheduleAdherenceSummary,
    summary="Task 12 — Schedule Adherence % [LIMITED_DATA]",
    description=(
        "[LIMITED_DATA] Schedule Adherence = Adherent Minutes / Scheduled Minutes × 100. "
        "Target >= 90%. Cannot compute without WFM scheduled start/end times per agent. "
        "Returns actual OCC/CFT/break minutes as partial data. "
        "Full adherence requires WFM Schedule Builder integration."
    ),
)
def get_schedule_adherence(
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

    agents_out: List[PartialAdherenceAgent] = []
    for rec in sorted(agg.values(), key=lambda r: r.agent_id):
        agents_out.append(PartialAdherenceAgent(
            agent_id=rec.agent_id,
            work_date=rec.work_date,
            team=rec.team,
            actual_present_hours=round(rec.present_hours, 3),
            actual_occ_minutes=round(rec.occ_minutes, 2),
            actual_cft_minutes=round(rec.cft_minutes, 2),
            actual_break_minutes=round(rec.break_minutes, 2),
            first_login=rec.first_login.strftime("%H:%M:%S") if rec.first_login else None,
            last_logout=rec.last_logout.strftime("%H:%M:%S") if rec.last_logout else None,
            shift_span_hours=round(rec.shift_span_hours, 3) if rec.shift_span_hours else None,
            scheduled_start=None,
            scheduled_end=None,
            scheduled_minutes=None,
            adherent_minutes=None,
            adherence_pct=None,
            adherence_status="INSUFFICIENT_DATA",
            data_limitation=(
                "Scheduled start/end not available. "
                "Connect WFM Schedule Builder to compute adherence %."
            ),
        ))

    return ScheduleAdherenceSummary(
        query_date=query_date,
        data_status=DATA_STATUS,
        total_agents=len(agents_out),
        agents_with_full_adherence_data=0,
        target_adherence_pct=ADHERENCE_TARGET_PCT,
        supervisor_flag_threshold=ADHERENCE_SUPERVISOR_FLAG_PCT,
        escalation_threshold=ADHERENCE_ESCALATE_PCT,
        agents=agents_out,
        adherence_formula=(
            "Schedule Adherence % = (Adherent Minutes / Scheduled Minutes) × 100. "
            "Adherent Minutes = minutes agent was in correct status "
            "(OCC/CFT when scheduled on-phones; break when scheduled on-break). "
            "Source: ops_task_2.pdf §9."
        ),
        missing_data=[
            "Scheduled start time per agent per day (WFM Schedule Builder)",
            "Scheduled end time per agent per day (WFM Schedule Builder)",
            "Scheduled break window times per agent (WFM Schedule Builder)",
            "Interval-level scheduled queue assignment (for 30-min granularity)",
        ],
        available_dates=available_dates(),
    )
