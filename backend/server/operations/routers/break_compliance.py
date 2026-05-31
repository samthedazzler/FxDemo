"""
Task 6 — Break Compliance Audit (Legal)
========================================
Reference: operations_task_1.pdf §6

Rule
----
  Irish Working Time Act (Organisation of Working Time Act 1997):
    - Any shift >= 6 hours requires a minimum 30-minute break.
    - Any shift >= 4.5 hours requires at least a 15-minute break.

  Compliance check:
    VIOLATION_6H:  shift_span_hours >= 6.0  AND  break_minutes < 30
    VIOLATION_4H:  shift_span_hours >= 4.5  AND  break_minutes < 15
    ZERO_BREAK:    break_minutes == 0.0     (entire shift with no break record)

  This is a LEGAL compliance task — not optional.
  Finance exposure: potential labour law penalties if violations are reported.

  NOTE on ZERO_BREAK detection:
    Some agents may have 0% shrinkage (0 break minutes) across a full shift.
    Per ops_task_1.pdf §6: "some full shifts with 0% shrinkage — meaning agents
    skipped mandated breaks." These are flagged for supervisor review.

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv  (break_minutes from Status Group = NaN rows)
  Limitation: break classification relies on status name ('break', 'lunch').
              If breaks are not logged as a status event, they appear as 0.

Endpoint
--------
  GET /api/operations/break-compliance
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

BREAK_30_MIN_SHIFT_HRS = 6.0   # 6h+ shift requires 30 min break
BREAK_15_MIN_SHIFT_HRS = 4.5   # 4.5h+ shift requires 15 min break
MIN_BREAK_FOR_6H = 30.0
MIN_BREAK_FOR_4H = 15.0


class BreakComplianceAgent(BaseModel):
    agent_id: str
    work_date: date
    team: str
    shift_span_hours: Optional[float]
    break_minutes: float
    lunch_included: bool
    violation_type: Optional[str]
    """VIOLATION_6H | VIOLATION_4H | ZERO_BREAK_FULL_SHIFT | None (compliant)."""
    is_compliant: bool
    legal_risk: str
    """HIGH | MEDIUM | NONE."""
    supervisor_action_required: bool


class BreakComplianceSummary(BaseModel):
    query_date: date
    total_agents: int
    compliant_agents: int
    violations: int
    high_risk_violations: int
    applicable_law: str
    agents: List[BreakComplianceAgent]
    available_dates: List[date]


@router.get(
    "/break-compliance",
    response_model=BreakComplianceSummary,
    summary="Task 6 — Break Compliance Audit (Irish Working Time Act)",
    description=(
        "Checks that agents working 6h+ had >= 30 min break, and agents working "
        "4.5h+ had >= 15 min break, per the Irish Organisation of Working Time Act 1997. "
        "Flags agents with zero break minutes across any full shift. "
        "This is a mandatory legal compliance check — violations require supervisor review."
    ),
)
def get_break_compliance(
    query_date: date = Query(..., description="Work date (YYYY-MM-DD).", example="2026-04-12"),
    agent_id: Optional[str] = Query(None),
):
    rows = get_rows()
    agg = build_agent_day_aggregates(rows, filter_date=query_date, filter_agent=agent_id)

    if not agg:
        dates = available_dates()
        raise HTTPException(
            status_code=404,
            detail={"message": f"No data for {query_date}.", "available_dates": [str(d) for d in dates]},
        )

    agents_out: List[BreakComplianceAgent] = []
    for rec in sorted(agg.values(), key=lambda r: r.agent_id):
        span = rec.shift_span_hours
        break_m = rec.break_minutes

        violation_type = None
        legal_risk = "NONE"

        if span is not None:
            if span >= BREAK_30_MIN_SHIFT_HRS and break_m < MIN_BREAK_FOR_6H:
                violation_type = "VIOLATION_6H"
                legal_risk = "HIGH"
            elif span >= BREAK_15_MIN_SHIFT_HRS and break_m < MIN_BREAK_FOR_4H:
                violation_type = "VIOLATION_4H"
                legal_risk = "MEDIUM"
        # Zero break on any logged shift
        if break_m == 0.0 and rec.present_hours >= 1.0 and violation_type is None:
            violation_type = "ZERO_BREAK_FULL_SHIFT"
            legal_risk = "MEDIUM"

        agents_out.append(BreakComplianceAgent(
            agent_id=rec.agent_id,
            work_date=rec.work_date,
            team=rec.team,
            shift_span_hours=round(span, 3) if span else None,
            break_minutes=round(break_m, 2),
            lunch_included=rec.break_minutes > 0,
            violation_type=violation_type,
            is_compliant=violation_type is None,
            legal_risk=legal_risk,
            supervisor_action_required=legal_risk in ("HIGH", "MEDIUM"),
        ))

    return BreakComplianceSummary(
        query_date=query_date,
        total_agents=len(agents_out),
        compliant_agents=sum(1 for a in agents_out if a.is_compliant),
        violations=sum(1 for a in agents_out if not a.is_compliant),
        high_risk_violations=sum(1 for a in agents_out if a.legal_risk == "HIGH"),
        applicable_law="Irish Organisation of Working Time Act 1997",
        agents=agents_out,
        available_dates=available_dates(),
    )
