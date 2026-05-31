"""
Task 10 — Replacement Decisions (Absence Coverage)
====================================================
Reference: operations_task_1.pdf §10

PURPOSE
-------
  When an agent is absent (sick call, emergency, approved leave), Operations must
  decide who covers their workload. This involves:
    - Identifying which agents are scheduled but not yet assigned
    - Matching skill/queue requirements for the absent agent's work
    - Considering overtime willingness and shift-swap rules
    - Confirming replacement does not violate break or hours compliance

  Decision logic (ops_task_1.pdf §10):
    1. Determine absent agent's scheduled queues/skills for the day
    2. Find available agents (scheduled but underloaded, or willing overtime)
    3. Filter by skill match (agent can handle the absent agent's queue)
    4. Rank by: spare capacity (highest OCC headroom first), then seniority
    5. Check replacement agent's hours won't breach Irish Working Time Act limits
    → Assign first eligible candidate; if none: escalate to supervisor

DATA STATUS: LIMITED — see DATA_REQUIREMENTS.md
-------------------------------------------------
  REQUIRED but NOT in current CSV:
    - Scheduled roster (which agent is scheduled for which shift/queue on each date)
    - Skill matrix (which queues/products each agent is trained for)
    - Real-time absence notifications (sick calls received today)
    - Overtime consent records (agents who agreed to be on standby)
    - Working time hours accumulation (weekly hours to check 48h WTA limit)

  THIS ENDPOINT CANNOT PRODUCE REAL DECISIONS without the above data.

Endpoint
--------
  GET /api/operations/replacement-decisions  [LIMITED_DATA]
"""

from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()

DATA_STATUS = "LIMITED_DATA"


class ReplacementDecisionLogic(BaseModel):
    step: int
    action: str
    data_required: str
    fallback_if_missing: str


class ReplacementDataRequirement(BaseModel):
    field: str
    source_system: str
    why_needed: str
    currently_available: bool


class ReplacementStubResponse(BaseModel):
    endpoint: str
    data_status: str
    summary: str
    decision_logic: List[ReplacementDecisionLogic]
    data_requirements: List[ReplacementDataRequirement]
    ranking_formula: str
    legal_constraint: str
    escalation_rule: str
    available_once_integrated: List[str]


@router.get(
    "/replacement-decisions",
    response_model=ReplacementStubResponse,
    summary="Task 10 — Replacement Decisions (Absence Coverage) [LIMITED_DATA]",
    description=(
        "[LIMITED_DATA] Determines which agent should cover for an absent colleague. "
        "Requires scheduled roster, skill matrix, and real-time absence data. "
        "Returns decision logic spec and data requirements."
    ),
)
def get_replacement_decisions(
    absent_agent_id: Optional[str] = Query(None, description="ID of the absent agent."),
    absence_date: Optional[date] = Query(None, description="Date of absence (YYYY-MM-DD)."),
):
    return ReplacementStubResponse(
        endpoint="GET /api/operations/replacement-decisions",
        data_status=DATA_STATUS,
        summary=(
            "Replacement Decision engine is not yet operational. "
            "Scheduled roster and skill matrix are required before candidates "
            "can be identified and ranked. Currently, the CSV provides actual "
            "attendance (who showed up) but not the planned schedule (who was meant to)."
        ),
        decision_logic=[
            ReplacementDecisionLogic(
                step=1,
                action="Look up absent agent's scheduled queues and skills for the day",
                data_required="Scheduled roster + skill matrix per agent",
                fallback_if_missing="Cannot determine what work needs covering",
            ),
            ReplacementDecisionLogic(
                step=2,
                action="Find agents scheduled today with available OCC headroom (occupancy < 80%)",
                data_required="Scheduled roster + live OCC data from CSV (available)",
                fallback_if_missing="Cannot identify underloaded agents without schedule",
            ),
            ReplacementDecisionLogic(
                step=3,
                action="Filter candidates by skill match for absent agent's queues",
                data_required="Skill / queue certification matrix per agent",
                fallback_if_missing="Cannot verify skill compatibility",
            ),
            ReplacementDecisionLogic(
                step=4,
                action="Check replacement won't breach 48h/week Irish Working Time Act limit",
                data_required="Rolling weekly hours accumulation per agent",
                fallback_if_missing="Legal compliance cannot be verified",
            ),
            ReplacementDecisionLogic(
                step=5,
                action="Rank eligible candidates: highest spare capacity first, then seniority",
                data_required="Agent seniority from HR records; live OCC from CSV (available)",
                fallback_if_missing="Cannot rank without seniority data",
            ),
        ],
        data_requirements=[
            ReplacementDataRequirement(
                field="scheduled_roster",
                source_system="WFM Schedule Builder (/api/schedule)",
                why_needed="Know which agents are scheduled today and their assigned queues",
                currently_available=False,
            ),
            ReplacementDataRequirement(
                field="skill_matrix",
                source_system="HR / Training records",
                why_needed="Confirm replacement agent can handle absent agent's queue type",
                currently_available=False,
            ),
            ReplacementDataRequirement(
                field="absence_notifications",
                source_system="Absence management / HR ticketing system",
                why_needed="Real-time sick call / emergency absence trigger for the decision",
                currently_available=False,
            ),
            ReplacementDataRequirement(
                field="weekly_hours_accumulation",
                source_system="CSV (partial — daily present_hours available)",
                why_needed="Ensure replacement doesn't breach 48h/week WTA 1997 limit",
                currently_available=True,
            ),
            ReplacementDataRequirement(
                field="overtime_consent",
                source_system="HR / agent preference records",
                why_needed="Only offer overtime to agents who have consented",
                currently_available=False,
            ),
        ],
        ranking_formula=(
            "Candidate score = (1 - agent_occupancy_pct/100) × 0.6 + seniority_score × 0.4. "
            "Higher score = better replacement candidate. "
            "agent_occupancy_pct is derivable from CSV (Task 5). "
            "seniority_score requires HR contract start date."
        ),
        legal_constraint=(
            "Irish Working Time Act 1997: max 48 hours/week averaged over 4 months. "
            "Replacement assignment must not push the agent's projected weekly total above 48h. "
            "Week-to-date present_hours are computable from CSV if full-week data is loaded."
        ),
        escalation_rule=(
            "If no eligible replacement found (all agents at capacity, skill mismatch, "
            "or hours limit breached): escalate to supervisor for manual assignment or "
            "consider cross-team borrowing. Log escalation in AuditLog."
        ),
        available_once_integrated=[
            "GET /api/operations/replacement-decisions?absent_agent_id=X&absence_date=YYYY-MM-DD",
            "Returns ranked list of candidate replacements with scores and compliance flags",
            "POST /api/operations/replacement-decisions/assign — confirm replacement selection",
        ],
    )
