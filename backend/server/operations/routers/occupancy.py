"""
Task 5 — OCC/CFT Breakdown & Occupancy Rate
============================================
Reference: operations_task_1.pdf §5, operations_task_2.pdf §3 (Occupancy Formula)

Formulas
--------
  Occupancy % = (OCC Minutes / Production Minutes) × 100
              = Transaction Hours / (Transaction + Available Hours) × 100
              (BEST WFM §1.4)

  Availability Rate % = (CFT Minutes / Production Minutes) × 100
                      = Available Hours / Production Hours × 100
                      (BEST WFM §1.4)

  Utilisation % = Production Hours / Present Hours × 100
                (BEST WFM §1.4)

  Target from ops_task_2.pdf §3:
    Occupancy % < 75% → flag as underutilised (routing/skill issue likely)
    Target < 85% per BEST WFM (to avoid burnout)
    Team average in CSV data ≈ 64.5%

  Interpretation:
    - Low OCC + High CFT → agent is idle; possible routing/skill assignment issue
    - High OCC (> 85%) → agent overloaded; burnout risk
    - Healthy range: 70–85%

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv

Endpoint
--------
  GET /api/operations/occupancy
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

OCC_LOW_THRESHOLD = 75.0
OCC_HIGH_THRESHOLD = 85.0


class AgentOccupancy(BaseModel):
    agent_id: str
    work_date: date
    team: str
    occ_minutes: float
    cft_minutes: float
    production_minutes: float
    occupancy_pct: Optional[float]
    """Occupancy = OCC / (OCC + CFT) × 100. BEST WFM §1.4 definition."""
    availability_rate_pct: Optional[float]
    """Availability Rate = CFT / (OCC + CFT) × 100."""
    utilisation_pct: Optional[float]
    """Utilisation = Production Hrs / Present Hrs × 100."""
    occupancy_status: str
    """LOW (< 75%) | HEALTHY (75–85%) | HIGH (> 85%)."""
    routing_flag: bool
    """True if occupancy < 75% — likely routing/skill assignment issue."""


class OccupancySummary(BaseModel):
    query_date: date
    total_agents: int
    team_avg_occupancy_pct: Optional[float]
    team_avg_utilisation_pct: Optional[float]
    wfm_occupancy_target_max: float
    agents_low_occupancy: int
    agents_overloaded: int
    agents: List[AgentOccupancy]
    available_dates: List[date]


@router.get(
    "/occupancy",
    response_model=OccupancySummary,
    summary="Task 5 — OCC/CFT Breakdown & Occupancy Rate",
    description=(
        "Returns OCC vs CFT minute split and derived Occupancy %, Availability Rate %, "
        "and Utilisation % per agent. Occupancy < 75% suggests routing/skill issues. "
        "Occupancy > 85% is a burnout risk per BEST WFM. Team average from current data ≈ 64.5%."
    ),
)
def get_occupancy(
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

    agents_out: List[AgentOccupancy] = []
    for rec in sorted(agg.values(), key=lambda r: r.agent_id):
        occ_pct = rec.occupancy_pct
        if occ_pct is None:
            occ_status = "NO_DATA"
            routing_flag = False
        elif occ_pct < OCC_LOW_THRESHOLD:
            occ_status = "LOW"
            routing_flag = True
        elif occ_pct > OCC_HIGH_THRESHOLD:
            occ_status = "HIGH"
            routing_flag = False
        else:
            occ_status = "HEALTHY"
            routing_flag = False

        agents_out.append(AgentOccupancy(
            agent_id=rec.agent_id,
            work_date=rec.work_date,
            team=rec.team,
            occ_minutes=round(rec.occ_minutes, 2),
            cft_minutes=round(rec.cft_minutes, 2),
            production_minutes=round(rec.production_minutes, 2),
            occupancy_pct=occ_pct,
            availability_rate_pct=rec.availability_rate_pct,
            utilisation_pct=rec.utilisation_pct,
            occupancy_status=occ_status,
            routing_flag=routing_flag,
        ))

    valid_occ = [a.occupancy_pct for a in agents_out if a.occupancy_pct is not None]
    valid_util = [a.utilisation_pct for a in agents_out if a.utilisation_pct is not None]
    avg_occ = round(sum(valid_occ) / len(valid_occ), 2) if valid_occ else None
    avg_util = round(sum(valid_util) / len(valid_util), 2) if valid_util else None

    return OccupancySummary(
        query_date=query_date,
        total_agents=len(agents_out),
        team_avg_occupancy_pct=avg_occ,
        team_avg_utilisation_pct=avg_util,
        wfm_occupancy_target_max=OCC_HIGH_THRESHOLD,
        agents_low_occupancy=sum(1 for a in agents_out if a.occupancy_status == "LOW"),
        agents_overloaded=sum(1 for a in agents_out if a.occupancy_status == "HIGH"),
        agents=agents_out,
        available_dates=available_dates(),
    )
