"""
Task 9 — Leave Grant Decisions
================================
Reference: operations_task_1.pdf §9

PURPOSE
-------
  Operations reviews WFM-approved leave requests and either grants or denies them,
  considering:
    - Agent's remaining leave entitlement balance
    - WFM leave allowance (max agents absent per day per team without SLA impact)
    - Blackout calendar (dates when no leave is permitted)
    - Concurrent absence threshold (% of team can be on leave simultaneously)

  Decision logic (ops_task_1.pdf §9):
    1. Agent has sufficient leave balance (entitlement_remaining >= requested_days)
    2. Team is not already at capacity (current_absent_count < max_concurrent_absent)
    3. Date is not in the blackout calendar
    → All three TRUE: GRANT; any FALSE: DENY with reason

  WFM Link:
    "Operations can only grant leave that WFM has pre-validated as capacity-safe."
    (ops_task_1.pdf §9) — WFM first runs Erlang/headcount check; Operations final-approves.

DATA STATUS: LIMITED — see DATA_REQUIREMENTS.md
-------------------------------------------------
  REQUIRED but NOT in current CSV:
    - Leave entitlement balances per agent (annual/sick/personal days remaining)
    - WFM leave allowance schedule (how many agents can be absent per team per day)
    - Blackout calendar (peak season dates, mandatory coverage dates)
    - Pending leave request queue (agent ID, start date, end date, leave type)
    - Already-approved concurrent absences per date

  THIS ENDPOINT CANNOT PRODUCE REAL DECISIONS without the above data.
  It returns a structured spec showing what the decision engine would evaluate.

Endpoint
--------
  GET /api/operations/leave-grant  [LIMITED_DATA]
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()

DATA_STATUS = "LIMITED_DATA"
MISSING_DATA = [
    "Leave entitlement balances per agent (annual/sick/personal days remaining)",
    "WFM leave allowance schedule (max concurrent absences per team per day)",
    "Blackout calendar (dates when leave cannot be approved)",
    "Pending leave request queue (agent_id, start_date, end_date, leave_type)",
    "Currently approved absences per date to check concurrent threshold",
]


class LeaveGrantDataRequirement(BaseModel):
    field: str
    source_system: str
    why_needed: str
    currently_available: bool


class LeaveGrantDecisionLogic(BaseModel):
    step: int
    condition: str
    pass_outcome: str
    fail_outcome: str
    data_required: str


class LeaveGrantStubResponse(BaseModel):
    endpoint: str
    data_status: str
    summary: str
    decision_logic: List[LeaveGrantDecisionLogic]
    data_requirements: List[LeaveGrantDataRequirement]
    formula_notes: str
    wfm_integration_note: str
    available_once_integrated: List[str]


@router.get(
    "/leave-grant",
    response_model=LeaveGrantStubResponse,
    summary="Task 9 — Leave Grant Decisions [LIMITED_DATA]",
    description=(
        "[LIMITED_DATA] Operations leave approval decision engine. "
        "Cannot produce real grant/deny decisions without leave entitlement balances, "
        "WFM allowance schedule, and blackout calendar. "
        "Returns the decision logic spec and data requirements."
    ),
)
def get_leave_grant(
    agent_id: Optional[str] = Query(None, description="Agent ID for targeted query."),
    request_date: Optional[date] = Query(None, description="Requested leave date (YYYY-MM-DD)."),
):
    return LeaveGrantStubResponse(
        endpoint="GET /api/operations/leave-grant",
        data_status=DATA_STATUS,
        summary=(
            "Leave Grant Decision engine is not yet operational. "
            "Three data sources are required before live decisions can be made: "
            "HR leave entitlement ledger, WFM capacity allowance schedule, and "
            "the Operations blackout calendar."
        ),
        decision_logic=[
            LeaveGrantDecisionLogic(
                step=1,
                condition="agent.leave_balance[leave_type] >= requested_days",
                pass_outcome="Agent has sufficient entitlement — continue to step 2",
                fail_outcome="DENY: INSUFFICIENT_BALANCE",
                data_required="HR Leave Entitlement Ledger (LeaveLedger table — partially exists in DB)",
            ),
            LeaveGrantDecisionLogic(
                step=2,
                condition="concurrent_absent_count(team, date) < wfm_max_concurrent_absent",
                pass_outcome="Team has capacity — continue to step 3",
                fail_outcome="DENY: TEAM_AT_CAPACITY",
                data_required="WFM leave allowance schedule + currently approved absences",
            ),
            LeaveGrantDecisionLogic(
                step=3,
                condition="request_date NOT IN blackout_calendar",
                pass_outcome="Date is not blacked out — GRANT",
                fail_outcome="DENY: BLACKOUT_DATE",
                data_required="Operations blackout calendar (peak season, mandatory coverage)",
            ),
        ],
        data_requirements=[
            LeaveGrantDataRequirement(
                field="leave_balance_remaining",
                source_system="HR / LeaveLedger DB table",
                why_needed="Step 1: verify agent has enough days of the requested leave type",
                currently_available=False,
            ),
            LeaveGrantDataRequirement(
                field="wfm_max_concurrent_absent",
                source_system="WFM Capacity Planner (Erlang-derived headcount floor)",
                why_needed="Step 2: ensure team stays above minimum required headcount",
                currently_available=False,
            ),
            LeaveGrantDataRequirement(
                field="blackout_dates",
                source_system="Operations / HR calendar system",
                why_needed="Step 3: block leave during peak periods or mandatory coverage dates",
                currently_available=False,
            ),
            LeaveGrantDataRequirement(
                field="pending_leave_requests",
                source_system="HR ticketing / leave management system",
                why_needed="Input queue — which agents have submitted leave requests",
                currently_available=False,
            ),
            LeaveGrantDataRequirement(
                field="approved_absences_by_date",
                source_system="HR / LeaveLedger (approved status filter)",
                why_needed="Count of already-approved absences to check concurrent threshold",
                currently_available=False,
            ),
        ],
        formula_notes=(
            "Concurrent Absence Threshold = floor(team_size × max_absence_pct). "
            "Typical WFM setting: max_absence_pct = 0.10 (10% of team). "
            "For a 20-agent team: max 2 agents absent simultaneously. "
            "WFM validates headcount safety first via Erlang C model before "
            "passing to Operations for final approval."
        ),
        wfm_integration_note=(
            "Per ops_task_1.pdf §9: Operations can only grant leave that WFM has "
            "pre-validated as capacity-safe. Flow: Agent requests leave → WFM runs "
            "Erlang headcount check → if capacity-safe, forwards to Operations queue → "
            "Operations checks entitlement + blackout → GRANT or DENY with reason."
        ),
        available_once_integrated=[
            "GET /api/operations/leave-grant?agent_id=X — return decision for one agent's pending request",
            "GET /api/operations/leave-grant?request_date=YYYY-MM-DD — show all pending requests for a date",
            "POST /api/operations/leave-grant/{request_id}/approve — approve a specific request",
            "POST /api/operations/leave-grant/{request_id}/deny?reason=... — deny with reason",
        ],
    )
