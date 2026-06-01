"""
Task 10 — Replacement Decisions (Absence Coverage)
====================================================
Reference: operations_task_1.pdf §10

Ranking formula:
  candidate_score = (1 - occupancy_pct/100) * 0.6 + overtime_consented * 0.4
  Higher score = better replacement candidate.

Data sources (operations/data/):
  absence_notifications.csv   — sick calls and emergency absences
  scheduled_roster.csv        — who is scheduled today
  skill_matrix.csv            — which queues each agent is certified for
  overtime_consent.csv        — agents willing to take extra shifts

Endpoint
--------
  GET /api/operations/replacement-decisions
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from operations.services.csv_loader import build_agent_day_aggregates, available_dates, get_rows
from operations.services.demo_data_loader import (
    _parse_date,
    agent_queues,
    get_absences,
    get_roster,
    overtime_consented,
    roster_entry,
    team_of_agent,
)

router = APIRouter()


class ReplacementCandidate(BaseModel):
    agent_id: str
    team: str
    queue_assignment: str
    occupancy_pct: Optional[float]
    spare_capacity_pct: Optional[float]
    overtime_consented: bool
    candidate_score: float
    certified_for_absent_queues: bool
    recommendation: str


class AbsenceInfo(BaseModel):
    notification_id: str
    agent_id: str
    absence_date: str
    absence_type: str
    notified_at: str
    absent_agent_queue: Optional[str]
    absent_agent_team: Optional[str]


class ReplacementDecisionResult(BaseModel):
    absence: AbsenceInfo
    candidates_evaluated: int
    top_candidate: Optional[ReplacementCandidate]
    all_candidates: List[ReplacementCandidate]
    decision: str
    decision_detail: str


class ReplacementSummary(BaseModel):
    query_date: str
    absences_found: int
    results: List[ReplacementDecisionResult]
    available_dates: List[date]


@router.get(
    "/replacement-decisions",
    response_model=ReplacementSummary,
    summary="Task 10 — Replacement Decisions (Absence Coverage)",
    description=(
        "Identifies and ranks replacement candidates for absent agents. "
        "Filters by skill match against the absent agent's queue. "
        "Scores candidates by spare OCC capacity and overtime consent. "
        "Data sourced from operations/data/ demo CSVs."
    ),
)
def get_replacement_decisions(
    absent_agent_id: Optional[str] = Query(None, description="Filter to a specific absent agent."),
    absence_date: Optional[date] = Query(
        None, description="Date of absence (YYYY-MM-DD). Defaults to first date in CSV."
    ),
):
    avail = available_dates()
    query_d = absence_date or avail[0]

    absences = get_absences()
    subset = [
        a for a in absences
        if _parse_date(a["absence_date"]) == query_d
        and (not absent_agent_id or a["agent_id"] == absent_agent_id)
    ]

    if not subset:
        # Return all absences in the dataset if none match the date
        subset = [
            a for a in absences
            if not absent_agent_id or a["agent_id"] == absent_agent_id
        ]
        if not subset:
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"No absence notifications found for agent={absent_agent_id} date={absence_date}.",
                    "available_dates": [str(d) for d in avail],
                },
            )

    # Load actual OCC data for the date to compute occupancy / spare capacity
    rows = get_rows()
    agg = build_agent_day_aggregates(rows, filter_date=query_d)
    occ_map = {rec.agent_id: rec.occupancy_pct for rec in agg.values()}

    results: List[ReplacementDecisionResult] = []

    for absence in subset:
        aid = absence["agent_id"]
        abs_date_str = absence["absence_date"]
        abs_date = _parse_date(abs_date_str) or query_d

        # Get absent agent's scheduled queue
        absent_roster = roster_entry(aid, abs_date)
        absent_queue = absent_roster["queue_assignment"] if absent_roster else None
        absent_team = team_of_agent(aid)

        # Build candidate pool: all agents scheduled that day (excluding the absent one)
        scheduled_today = [
            r for r in get_roster()
            if _parse_date(r["schedule_date"]) == abs_date
            and r["agent_id"] != aid
            and r["roster_status"] == "SCHEDULED"
        ]

        candidates: List[ReplacementCandidate] = []
        for sched in scheduled_today:
            c_id = sched["agent_id"]
            c_queues = agent_queues(c_id)
            certified = (absent_queue in c_queues) if absent_queue else True
            occ = occ_map.get(c_id)
            spare = round(100 - occ, 1) if occ is not None else None
            ot = overtime_consented(c_id)

            # Score: 60% spare capacity + 40% overtime consent
            cap_score = (spare / 100) if spare is not None else 0.5
            score = round(cap_score * 0.6 + (1.0 if ot else 0.0) * 0.4, 4)

            rec = "ELIGIBLE" if certified else "INELIGIBLE: skill mismatch"
            candidates.append(ReplacementCandidate(
                agent_id=c_id,
                team=sched["team"],
                queue_assignment=sched["queue_assignment"],
                occupancy_pct=occ,
                spare_capacity_pct=spare,
                overtime_consented=ot,
                candidate_score=score,
                certified_for_absent_queues=certified,
                recommendation=rec,
            ))

        # Sort: eligible first, then by score descending
        eligible = sorted(
            [c for c in candidates if c.certified_for_absent_queues],
            key=lambda c: c.candidate_score, reverse=True
        )
        ineligible = [c for c in candidates if not c.certified_for_absent_queues]
        ranked = eligible + ineligible

        top = eligible[0] if eligible else None
        decision = "REPLACEMENT_FOUND" if top else "ESCALATE_TO_SUPERVISOR"
        detail = (
            f"Top candidate: {top.agent_id} (score={top.candidate_score}, "
            f"spare={top.spare_capacity_pct}%, OT_consent={top.overtime_consented})"
            if top else
            "No eligible replacement found — all scheduled agents lack required queue certification."
        )

        results.append(ReplacementDecisionResult(
            absence=AbsenceInfo(
                notification_id=absence["notification_id"],
                agent_id=aid,
                absence_date=abs_date_str,
                absence_type=absence["absence_type"],
                notified_at=absence["notified_at"],
                absent_agent_queue=absent_queue,
                absent_agent_team=absent_team,
            ),
            candidates_evaluated=len(candidates),
            top_candidate=top,
            all_candidates=ranked,
            decision=decision,
            decision_detail=detail,
        ))

    return ReplacementSummary(
        query_date=str(query_d),
        absences_found=len(results),
        results=results,
        available_dates=avail,
    )
