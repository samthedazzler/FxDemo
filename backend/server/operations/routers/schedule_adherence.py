"""
Task 12 — Schedule Adherence %
================================
Reference: operations_task_1.pdf §12, operations_task_2.pdf §9

Formula:
  Schedule Adherence % = (Adherent Minutes / Scheduled Minutes) × 100

  Adherent Minutes = minutes the agent was logged in during their scheduled window
                     (first_login to last_logout clamped to scheduled_start–scheduled_end)

  Scheduled Minutes = scheduled_end − scheduled_start (in minutes)

Thresholds:
  >= 90%: ON_TARGET
  85–89%: SUPERVISOR_REVIEW
  < 85%:  MANAGER_ESCALATION

Data sources:
  Main CSV (actual login/logout, OCC/CFT/break minutes) — always available
  operations/data/scheduled_roster.csv — scheduled start/end per agent per day

Endpoint
--------
  GET /api/operations/schedule-adherence
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from operations.services.csv_loader import build_agent_day_aggregates, available_dates, get_rows
from operations.services.demo_data_loader import _parse_date, get_roster

router = APIRouter()

ADHERENCE_TARGET = 90.0
ADHERENCE_SUPERVISOR = 85.0
ADHERENCE_ESCALATE = 75.0


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


class AgentAdherence(BaseModel):
    agent_id: str
    work_date: date
    team: str
    # Scheduled (from roster CSV)
    scheduled_start: Optional[str]
    scheduled_end: Optional[str]
    scheduled_minutes: Optional[float]
    # Actual (from main CSV)
    actual_first_login: Optional[str]
    actual_last_logout: Optional[str]
    actual_present_hours: float
    actual_occ_minutes: float
    actual_break_minutes: float
    # Computed
    adherent_minutes: Optional[float]
    adherence_pct: Optional[float]
    late_start_minutes: Optional[float]
    early_departure_minutes: Optional[float]
    adherence_status: str
    data_complete: bool


class AdherenceSummary(BaseModel):
    query_date: date
    total_agents: int
    agents_on_target: int
    agents_supervisor_review: int
    agents_manager_escalation: int
    agents_no_data: int
    team_avg_adherence_pct: Optional[float]
    adherence_formula: str
    agents: List[AgentAdherence]
    available_dates: List[date]


@router.get(
    "/schedule-adherence",
    response_model=AdherenceSummary,
    summary="Task 12 — Schedule Adherence %",
    description=(
        "Computes Schedule Adherence % = Adherent Minutes / Scheduled Minutes × 100. "
        "Cross-references actual login/logout (main CSV) against planned schedule (scheduled_roster.csv). "
        "Flags agents below 90% target. Also shows late-start and early-departure deltas."
    ),
)
def get_schedule_adherence(
    query_date: date = Query(..., description="Work date (YYYY-MM-DD).", example="2026-04-13"),
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

    # Build roster lookup for this date
    roster_map: dict = {}
    for r in get_roster():
        if _parse_date(r["schedule_date"]) == query_date:
            roster_map[r["agent_id"]] = r

    agents_out: List[AgentAdherence] = []

    for rec in sorted(agg.values(), key=lambda r: r.agent_id):
        sched = roster_map.get(rec.agent_id)

        sched_start_dt = _parse_dt(sched["scheduled_start"]) if sched else None
        sched_end_dt = _parse_dt(sched["scheduled_end"]) if sched else None

        sched_minutes: Optional[float] = None
        adherent_minutes: Optional[float] = None
        adherence_pct: Optional[float] = None
        late_start_min: Optional[float] = None
        early_dep_min: Optional[float] = None
        data_complete = False

        if sched_start_dt and sched_end_dt:
            sched_minutes = (sched_end_dt - sched_start_dt).total_seconds() / 60.0

            actual_login = rec.first_login
            actual_logout = rec.last_logout

            if actual_login and actual_logout:
                data_complete = True

                # Clamp actual login/logout to scheduled window
                adherent_start = max(actual_login, sched_start_dt)
                adherent_end = min(actual_logout, sched_end_dt)
                adherent_raw = max(0.0, (adherent_end - adherent_start).total_seconds() / 60.0)
                # Subtract break minutes (breaks don't count against adherence)
                adherent_minutes = round(max(0.0, adherent_raw - rec.break_minutes), 2)

                # Cap at scheduled minutes
                scheduled_productive = sched_minutes - 30.0  # subtract scheduled break
                adherent_minutes = min(adherent_minutes, scheduled_productive)

                adherence_pct = round(adherent_minutes / scheduled_productive * 100, 2) if scheduled_productive > 0 else None

                # Late start (positive = arrived late)
                late_start_min = round((actual_login - sched_start_dt).total_seconds() / 60.0, 1)
                late_start_min = max(0.0, late_start_min)

                # Early departure (positive = left early)
                early_dep_min = round((sched_end_dt - actual_logout).total_seconds() / 60.0, 1)
                early_dep_min = max(0.0, early_dep_min)

        if adherence_pct is None:
            status = "INSUFFICIENT_DATA"
        elif adherence_pct >= ADHERENCE_TARGET:
            status = "ON_TARGET"
        elif adherence_pct >= ADHERENCE_SUPERVISOR:
            status = "SUPERVISOR_REVIEW"
        else:
            status = "MANAGER_ESCALATION"

        agents_out.append(AgentAdherence(
            agent_id=rec.agent_id,
            work_date=rec.work_date,
            team=rec.team,
            scheduled_start=sched["scheduled_start"] if sched else None,
            scheduled_end=sched["scheduled_end"] if sched else None,
            scheduled_minutes=round(sched_minutes, 2) if sched_minutes else None,
            actual_first_login=rec.first_login.strftime("%H:%M:%S") if rec.first_login else None,
            actual_last_logout=rec.last_logout.strftime("%H:%M:%S") if rec.last_logout else None,
            actual_present_hours=round(rec.present_hours, 3),
            actual_occ_minutes=round(rec.occ_minutes, 2),
            actual_break_minutes=round(rec.break_minutes, 2),
            adherent_minutes=adherent_minutes,
            adherence_pct=adherence_pct,
            late_start_minutes=late_start_min,
            early_departure_minutes=early_dep_min,
            adherence_status=status,
            data_complete=data_complete,
        ))

    valid_pcts = [a.adherence_pct for a in agents_out if a.adherence_pct is not None]
    avg_pct = round(sum(valid_pcts) / len(valid_pcts), 2) if valid_pcts else None

    return AdherenceSummary(
        query_date=query_date,
        total_agents=len(agents_out),
        agents_on_target=sum(1 for a in agents_out if a.adherence_status == "ON_TARGET"),
        agents_supervisor_review=sum(1 for a in agents_out if a.adherence_status == "SUPERVISOR_REVIEW"),
        agents_manager_escalation=sum(1 for a in agents_out if a.adherence_status == "MANAGER_ESCALATION"),
        agents_no_data=sum(1 for a in agents_out if a.adherence_status == "INSUFFICIENT_DATA"),
        team_avg_adherence_pct=avg_pct,
        adherence_formula=(
            "Adherence % = Adherent Minutes / Scheduled Productive Minutes × 100. "
            "Adherent Minutes = login-to-logout clamped to scheduled window, minus break minutes. "
            "Scheduled Productive Minutes = (scheduled_end - scheduled_start) - 30 min break."
        ),
        agents=agents_out,
        available_dates=available_dates(),
    )
