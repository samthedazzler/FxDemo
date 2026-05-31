"""
Task 11 — Shift Swap Management
================================
Reference: operations_task_1.pdf §11

PURPOSE
-------
  Agents may request to swap their scheduled shift with another agent.
  Operations validates that:
    1. Both agents are scheduled on the target dates
    2. Skill/queue equivalence: the swap doesn't leave a queue uncovered
    3. Neither agent's resulting hours violate Working Time Act 1997 limits
    4. The swap doesn't create a coverage gap on either date (WFM headcount floor)

  Approval logic (ops_task_1.pdf §11):
    APPROVE if:
      - Both agents scheduled on their respective dates       (needs roster)
      - Agent A can cover Agent B's queue (and vice versa)    (needs skill matrix)
      - No Working Time Act breach for either agent           (needs rolling hours)
      - Neither date drops below minimum coverage threshold   (needs WFM schedule floor)
    DENY if any condition fails (with specific reason code)

DATA STATUS: LIMITED — see DATA_REQUIREMENTS.md
-------------------------------------------------
  REQUIRED but NOT in current CSV:
    - Scheduled roster (which agent is on which shift/date)
    - Skill/queue matrix (cross-coverage eligibility)
    - Pending shift-swap request queue
    - WFM minimum coverage per date (headcount floor)
    - Rolling weekly hours per agent (Working Time Act compliance)

  THIS ENDPOINT CANNOT PRODUCE REAL DECISIONS without the above data.

Endpoint
--------
  GET /api/operations/shift-swap  [LIMITED_DATA]
"""

from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()

DATA_STATUS = "LIMITED_DATA"


class SwapValidationStep(BaseModel):
    check: str
    condition: str
    deny_code_if_fail: str
    data_required: str
    currently_available: bool


class ShiftSwapDataRequirement(BaseModel):
    field: str
    source_system: str
    why_needed: str
    currently_available: bool


class ShiftSwapStubResponse(BaseModel):
    endpoint: str
    data_status: str
    summary: str
    validation_steps: List[SwapValidationStep]
    data_requirements: List[ShiftSwapDataRequirement]
    approval_logic: str
    working_time_constraint: str
    available_once_integrated: List[str]


@router.get(
    "/shift-swap",
    response_model=ShiftSwapStubResponse,
    summary="Task 11 — Shift Swap Management [LIMITED_DATA]",
    description=(
        "[LIMITED_DATA] Validates and approves/denies agent shift-swap requests. "
        "Requires scheduled roster, skill matrix, and WFM headcount floors. "
        "Returns the validation logic spec and data requirements."
    ),
)
def get_shift_swap(
    agent_a: Optional[str] = Query(None, description="Agent requesting the swap."),
    agent_b: Optional[str] = Query(None, description="Agent being swapped with."),
    agent_a_date: Optional[date] = Query(None, description="Date Agent A wants to give away."),
    agent_b_date: Optional[date] = Query(None, description="Date Agent B wants to give away."),
):
    return ShiftSwapStubResponse(
        endpoint="GET /api/operations/shift-swap",
        data_status=DATA_STATUS,
        summary=(
            "Shift Swap Management is not yet operational. "
            "The scheduled roster is the critical missing input — without it, "
            "we cannot verify that both agents are scheduled on the target dates, "
            "nor check that coverage thresholds are maintained. "
            "OCC and present hours from the CSV are available to support the "
            "Working Time Act hours check once the roster is connected."
        ),
        validation_steps=[
            SwapValidationStep(
                check="Both agents are scheduled",
                condition="agent_a IN roster[agent_b_date] AND agent_b IN roster[agent_a_date]",
                deny_code_if_fail="DENY: AGENT_NOT_SCHEDULED",
                data_required="WFM Scheduled Roster",
                currently_available=False,
            ),
            SwapValidationStep(
                check="Skill cross-coverage",
                condition="agent_a.skills ⊇ agent_b.queues AND agent_b.skills ⊇ agent_a.queues",
                deny_code_if_fail="DENY: SKILL_MISMATCH",
                data_required="Skill / Queue Certification Matrix",
                currently_available=False,
            ),
            SwapValidationStep(
                check="Working Time Act hours limit",
                condition="projected_weekly_hours(agent_a) <= 48 AND projected_weekly_hours(agent_b) <= 48",
                deny_code_if_fail="DENY: HOURS_LIMIT_BREACH",
                data_required="Rolling weekly present_hours (CSV provides daily; aggregation needed)",
                currently_available=True,
            ),
            SwapValidationStep(
                check="Coverage floor maintained on both dates",
                condition=(
                    "active_agents(agent_a_date) - 1 >= wfm_floor(agent_a_date) AND "
                    "active_agents(agent_b_date) - 1 >= wfm_floor(agent_b_date)"
                ),
                deny_code_if_fail="DENY: COVERAGE_FLOOR_BREACH",
                data_required="WFM minimum headcount floor per date (Erlang-derived)",
                currently_available=False,
            ),
        ],
        data_requirements=[
            ShiftSwapDataRequirement(
                field="scheduled_roster",
                source_system="WFM Schedule Builder (/api/schedule)",
                why_needed="Verify both agents are scheduled and on which queues",
                currently_available=False,
            ),
            ShiftSwapDataRequirement(
                field="skill_matrix",
                source_system="HR / Training records",
                why_needed="Cross-coverage eligibility check for swap equivalence",
                currently_available=False,
            ),
            ShiftSwapDataRequirement(
                field="swap_request_queue",
                source_system="Operations workflow / ticketing system",
                why_needed="Input: pending swap requests to process",
                currently_available=False,
            ),
            ShiftSwapDataRequirement(
                field="wfm_coverage_floor",
                source_system="WFM Capacity Planner (Erlang-derived minimum headcount)",
                why_needed="Ensure swap doesn't drop either date below minimum staffing",
                currently_available=False,
            ),
            ShiftSwapDataRequirement(
                field="rolling_weekly_hours",
                source_system="CSV Agent_Breakdown_140426.csv (present_hours aggregated weekly)",
                why_needed="Irish Working Time Act 1997 compliance — 48h/week limit",
                currently_available=True,
            ),
        ],
        approval_logic=(
            "ALL four checks must pass for APPROVE. "
            "First failing check generates a specific DENY code and reason. "
            "Multiple failures are all returned so the agent understands all blockers. "
            "Approved swaps must update the roster in WFM Schedule Builder and "
            "be recorded in AuditLog for HR compliance."
        ),
        working_time_constraint=(
            "Irish Working Time Act 1997 §15: maximum 48 average hours per week "
            "calculated over a 4-month reference period. "
            "The swap adds the swapped-in shift to the agent's projected weekly total. "
            "Formula: projected_hours = week_to_date_present_hours + swap_shift_duration. "
            "If projected_hours > 48, the swap must be denied unless agent opts into "
            "derogation agreement (requires HR sign-off)."
        ),
        available_once_integrated=[
            "GET /api/operations/shift-swap?agent_a=X&agent_b=Y&agent_a_date=D1&agent_b_date=D2 — validate swap eligibility",
            "POST /api/operations/shift-swap/approve — approve swap and update roster",
            "POST /api/operations/shift-swap/deny?reason=... — deny with reason code",
            "GET /api/operations/shift-swap/pending — list all pending swap requests",
        ],
    )
