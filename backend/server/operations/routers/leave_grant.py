"""
Task 9 — Leave Grant Decisions
================================
Reference: operations_task_1.pdf §9

Decision logic (3 steps, all must pass for GRANT):
  Step 1 — Balance check:   agent.leave_balance[type] >= days_requested
  Step 2 — Capacity check:  concurrent_approved_absences(team, date) < wfm_max_concurrent
  Step 3 — Blackout check:  request_date NOT IN blackout_calendar

Data sources (operations/data/):
  leave_requests.csv        — pending request queue
  leave_entitlements.csv    — per-agent balance
  wfm_leave_allowance.csv   — max concurrent absences per team per date
  blackout_calendar.csv     — blacked-out date ranges

Endpoint
--------
  GET /api/operations/leave-grant
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from operations.services.demo_data_loader import (
    _parse_date,
    approved_absent_count,
    balance,
    get_leave_requests,
    is_blackout,
    max_concurrent_absent,
    team_of_agent,
)

router = APIRouter()


class DecisionStep(BaseModel):
    step: int
    condition: str
    result: str
    detail: str


class LeaveDecision(BaseModel):
    request_id: str
    agent_id: str
    leave_type: str
    start_date: str
    end_date: str
    days_requested: float
    submitted_at: str
    decision: str
    deny_reason: Optional[str]
    steps: List[DecisionStep]
    balance_before: float
    balance_after: Optional[float]


class LeaveGrantSummary(BaseModel):
    total_evaluated: int
    granted: int
    denied: int
    decisions: List[LeaveDecision]


@router.get(
    "/leave-grant",
    response_model=LeaveGrantSummary,
    summary="Task 9 — Leave Grant Decisions",
    description=(
        "Evaluates pending leave requests through a 3-step decision engine: "
        "(1) balance check, (2) team capacity check, (3) blackout calendar check. "
        "Returns GRANT or DENY with the failing step highlighted. "
        "Data sourced from operations/data/ demo CSVs."
    ),
)
def get_leave_grant(
    agent_id: Optional[str] = Query(None, description="Filter to a specific agent's requests."),
    request_date: Optional[date] = Query(
        None,
        description=(
            "Filter to requests that start on or after this date (YYYY-MM-DD). "
            "Leave blank to evaluate ALL pending requests."
        ),
    ),
    status_filter: str = Query(
        "PENDING",
        description="Which requests to evaluate: PENDING | ALL | APPROVED | DENIED",
    ),
):
    all_requests = get_leave_requests()

    subset = []
    for r in all_requests:
        if status_filter != "ALL" and r["status"] != status_filter:
            continue
        if agent_id and r["agent_id"] != agent_id:
            continue
        if request_date:
            start = _parse_date(r["start_date"])
            if not (start and start >= request_date):
                continue
        subset.append(r)

    decisions: List[LeaveDecision] = []

    for r in subset:
        aid = r["agent_id"]
        leave_type = r["leave_type"]
        days_req = float(r["days_requested"])
        start_d = _parse_date(r["start_date"])
        team = team_of_agent(aid)
        bal = balance(aid, leave_type)

        steps: List[DecisionStep] = []
        deny_reason: Optional[str] = None

        # Step 1 — balance
        if bal >= days_req:
            steps.append(DecisionStep(
                step=1,
                condition=f"leave_balance[{leave_type}] ({bal} days) >= requested ({days_req} days)",
                result="PASS",
                detail=f"Agent has {bal} {leave_type} days remaining.",
            ))
        else:
            steps.append(DecisionStep(
                step=1,
                condition=f"leave_balance[{leave_type}] ({bal} days) >= requested ({days_req} days)",
                result="FAIL",
                detail=f"Only {bal} days remaining — {days_req} days requested. Insufficient balance.",
            ))
            deny_reason = "INSUFFICIENT_BALANCE"

        # Step 2 — team capacity (only if step 1 passed)
        if deny_reason is None:
            check_d = start_d or request_date or date.today()
            approved_count = approved_absent_count(team or "", check_d) if team else 0
            max_absent = max_concurrent_absent(team or "", check_d)
            limit = max_absent if max_absent is not None else 1

            if approved_count < limit:
                steps.append(DecisionStep(
                    step=2,
                    condition=f"concurrent_absent ({approved_count}) < wfm_max ({limit})",
                    result="PASS",
                    detail=f"{approved_count} agent(s) already approved absent on {check_d}. Limit is {limit}.",
                ))
            else:
                steps.append(DecisionStep(
                    step=2,
                    condition=f"concurrent_absent ({approved_count}) < wfm_max ({limit})",
                    result="FAIL",
                    detail=(
                        f"Team already has {approved_count} approved absence(s) on {check_d}. "
                        f"WFM limit is {limit}. Team is at capacity."
                    ),
                ))
                deny_reason = "TEAM_AT_CAPACITY"

        # Step 3 — blackout (only if step 2 passed)
        if deny_reason is None:
            check_d = start_d or request_date or date.today()
            blackout_hit = is_blackout(check_d)
            if blackout_hit is None:
                steps.append(DecisionStep(
                    step=3,
                    condition=f"{check_d} NOT IN blackout_calendar",
                    result="PASS",
                    detail=f"{check_d} is not a blacked-out date.",
                ))
            else:
                steps.append(DecisionStep(
                    step=3,
                    condition=f"{check_d} NOT IN blackout_calendar",
                    result="FAIL",
                    detail=f"{check_d} falls within a blackout period: {blackout_hit}.",
                ))
                deny_reason = f"BLACKOUT_DATE: {blackout_hit}"

        decision = "DENY" if deny_reason else "GRANT"

        decisions.append(LeaveDecision(
            request_id=r["request_id"],
            agent_id=aid,
            leave_type=leave_type,
            start_date=r["start_date"],
            end_date=r["end_date"],
            days_requested=days_req,
            submitted_at=r["submitted_at"],
            decision=decision,
            deny_reason=deny_reason,
            steps=steps,
            balance_before=bal,
            balance_after=round(bal - days_req, 1) if decision == "GRANT" else None,
        ))

    granted = sum(1 for d in decisions if d.decision == "GRANT")

    return LeaveGrantSummary(
        total_evaluated=len(decisions),
        granted=granted,
        denied=len(decisions) - granted,
        decisions=decisions,
    )
