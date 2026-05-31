"""
Task 3 — Anomaly Detection: Flagging Underperformers
=====================================================
Reference: operations_task_1.pdf §3, operations_task_2.pdf §3 (Underperformance Detection)

Formulas
--------
  Productivity % = (Productive Hours / Present Hours) × 100
    Flag if Productivity % < 85%   (ops_task_2.pdf threshold)

  Occupancy %    = (OCC Minutes / Production Minutes) × 100
    Flag if Occupancy % < 75%      (ops_task_2.pdf threshold)

  Z-score (occupancy):
    z = (agent_occ_pct − team_mean_occ_pct) / team_std_occ_pct
    Flag if z < −2.0  (statistically significantly below average)
    Context: agent …725249 at 6.1% OCC is 10× below team average per task doc

  Disappearance detection:
    Agent present on Day 1 but missing entirely from Day 2+
    (ops_task_1.pdf §3 mentions agent …484348 disappearing after Day 1)

  Composite Performance Score (ops_task_2.pdf §4 — Layoff/Offboarding Logic):
    Performance Score =
      0.40 × Productivity %
    + 0.30 × Adherence %       ← MISSING DATA (needs scheduled shift)
    + 0.20 × Quality %         ← MISSING DATA (needs QA scores)
    + 0.10 × Attendance %      ← MISSING DATA (needs absence records)

    Decision:
      >= 90 → Top Performer
      80–89 → Meets Expectations
      70–79 → Coaching Required
      60–69 → PIP
      <  60 → Offboarding Review

    NOTE: Full composite score cannot be computed from CSV alone.
    Partial score uses only available components; missing fields are noted.

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv  (3 days: Apr 12–14)

Endpoint
--------
  GET /api/operations/anomaly-detection
"""

import math
import statistics
from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from operations.services.csv_loader import (
    build_agent_day_aggregates,
    available_dates,
    get_rows,
)

router = APIRouter()

PRODUCTIVITY_THRESHOLD = 85.0
OCCUPANCY_THRESHOLD = 75.0
Z_SCORE_THRESHOLD = -2.0


class UnderperformanceFlag(BaseModel):
    reason: str
    value: Optional[float]
    threshold: Optional[float]


class AgentAnomaly(BaseModel):
    agent_id: str
    work_date: date
    team: str
    occ_minutes: float
    productivity_pct: Optional[float]
    occupancy_pct: Optional[float]
    z_score_occupancy: Optional[float]
    """Z-score vs team mean. < -2.0 is statistically abnormal."""
    flags: List[UnderperformanceFlag]
    is_flagged: bool
    recommended_action: str
    """Coaching | Warning | PIP | Offboarding Review | Monitor."""
    partial_performance_score: Optional[float]
    """Weighted partial score using only available metrics (40% Productivity + 15% Occupancy proxy).
    Missing: Adherence (30%), Quality (20%), Attendance (10%)."""
    missing_score_components: List[str]


class DisappearedAgent(BaseModel):
    agent_id: str
    last_seen_date: date
    missing_dates: List[date]


class AnomalyDetectionResult(BaseModel):
    query_date: date
    total_agents_today: int
    flagged_agents: int
    team_mean_occupancy_pct: Optional[float]
    team_std_occupancy_pct: Optional[float]
    agents: List[AgentAnomaly]
    disappeared_agents: List[DisappearedAgent]
    available_dates: List[date]


def _recommended_action(flags: List[UnderperformanceFlag]) -> str:
    if not flags:
        return "Monitor"
    reasons = {f.reason for f in flags}
    if "PRODUCTIVITY_BELOW_85" in reasons or "Z_SCORE_CRITICAL" in reasons:
        return "Coaching"
    if "OCCUPANCY_BELOW_75" in reasons:
        return "Coaching"
    return "Monitor"


def _partial_score(productivity_pct: Optional[float], occupancy_pct: Optional[float]) -> Optional[float]:
    """Partial performance score using only available CSV metrics.
    Full formula: 0.40*Prod + 0.30*Adherence + 0.20*Quality + 0.10*Attendance
    Available: 0.40*Prod + 0.15*Occupancy (proxy for utilisation)
    Missing components are excluded; result scaled to note it's partial.
    """
    if productivity_pct is None:
        return None
    # Use Productivity (40%) + Occupancy as proxy (15%) — normalised to available weight
    score = 0.40 * productivity_pct
    if occupancy_pct is not None:
        score += 0.15 * occupancy_pct
    return round(score, 2)


@router.get(
    "/anomaly-detection",
    response_model=AnomalyDetectionResult,
    summary="Task 3 — Anomaly Detection: Flag Underperforming Agents",
    description=(
        "Identifies agents below performance thresholds using Z-score analysis "
        "and rule-based flags. Productivity < 85% or Occupancy < 75% triggers a flag. "
        "Z-score < -2.0 flags statistically abnormal underperformance. "
        "Also detects agents who disappeared across days."
    ),
)
def get_anomaly_detection(
    query_date: date = Query(..., description="Work date to analyse (YYYY-MM-DD).", example="2026-04-12"),
):
    rows = get_rows()
    all_dates = available_dates()

    # Aggregates for query date
    agg_today = build_agent_day_aggregates(rows, filter_date=query_date)
    # Aggregates for all dates (disappearance detection)
    agg_all = build_agent_day_aggregates(rows)

    if not agg_today:
        return AnomalyDetectionResult(
            query_date=query_date,
            total_agents_today=0,
            flagged_agents=0,
            team_mean_occupancy_pct=None,
            team_std_occupancy_pct=None,
            agents=[],
            disappeared_agents=[],
            available_dates=all_dates,
        )

    # Compute team-level occupancy stats for Z-score
    occ_pcts = [r.occupancy_pct for r in agg_today.values() if r.occupancy_pct is not None]
    mean_occ = statistics.mean(occ_pcts) if occ_pcts else None
    std_occ = statistics.stdev(occ_pcts) if len(occ_pcts) > 1 else None

    agents_out: List[AgentAnomaly] = []
    for rec in sorted(agg_today.values(), key=lambda r: r.agent_id):
        flags: List[UnderperformanceFlag] = []
        prod_pct = rec.productivity_pct
        occ_pct = rec.occupancy_pct

        # Z-score
        z = None
        if mean_occ is not None and std_occ is not None and occ_pct is not None:
            z = round((occ_pct - mean_occ) / std_occ, 3) if std_occ > 0 else 0.0

        if prod_pct is not None and prod_pct < PRODUCTIVITY_THRESHOLD:
            flags.append(UnderperformanceFlag(
                reason="PRODUCTIVITY_BELOW_85",
                value=prod_pct,
                threshold=PRODUCTIVITY_THRESHOLD,
            ))
        if occ_pct is not None and occ_pct < OCCUPANCY_THRESHOLD:
            flags.append(UnderperformanceFlag(
                reason="OCCUPANCY_BELOW_75",
                value=occ_pct,
                threshold=OCCUPANCY_THRESHOLD,
            ))
        if z is not None and z < Z_SCORE_THRESHOLD:
            flags.append(UnderperformanceFlag(
                reason="Z_SCORE_CRITICAL",
                value=z,
                threshold=Z_SCORE_THRESHOLD,
            ))

        agents_out.append(AgentAnomaly(
            agent_id=rec.agent_id,
            work_date=rec.work_date,
            team=rec.team,
            occ_minutes=round(rec.occ_minutes, 2),
            productivity_pct=prod_pct,
            occupancy_pct=occ_pct,
            z_score_occupancy=z,
            flags=flags,
            is_flagged=len(flags) > 0,
            recommended_action=_recommended_action(flags),
            partial_performance_score=_partial_score(prod_pct, occ_pct),
            missing_score_components=["Adherence % (30%)", "Quality % (20%)", "Attendance % (10%)"],
        ))

    # Disappearance detection
    agents_today = {r.agent_id for r in agg_today.values()}
    agents_all_dates: Dict[str, List[date]] = {}
    for (agent_id, d), _ in agg_all.items():
        agents_all_dates.setdefault(agent_id, []).append(d)

    disappeared: List[DisappearedAgent] = []
    if all_dates:
        for agent_id, seen_dates in agents_all_dates.items():
            last_seen = max(seen_dates)
            full_range = all_dates
            missing = [d for d in full_range if d > last_seen]
            if missing:
                disappeared.append(DisappearedAgent(
                    agent_id=agent_id,
                    last_seen_date=last_seen,
                    missing_dates=missing,
                ))

    return AnomalyDetectionResult(
        query_date=query_date,
        total_agents_today=len(agents_out),
        flagged_agents=sum(1 for a in agents_out if a.is_flagged),
        team_mean_occupancy_pct=round(mean_occ, 2) if mean_occ is not None else None,
        team_std_occupancy_pct=round(std_occ, 2) if std_occ is not None else None,
        agents=agents_out,
        disappeared_agents=disappeared,
        available_dates=all_dates,
    )
