"""
Task 8 — Trend Analysis on Agent Performance
=============================================
Reference: operations_task_1.pdf §8

Purpose
-------
  With 3 days of data (Apr 12–14), build per-agent rolling performance trends:
    - Who is declining in OCC% (occupancy)?
    - Who is increasing in shrinkage?
    - Who shows consistent underperformance?
    - Early signals of attrition/disengagement for WFM

Trend Direction Algorithm
--------------------------
  For each metric over the 3 available days:

  Linear slope: slope = Σ((xi − x̄)(yi − ȳ)) / Σ((xi − x̄)²)
    where xi = day index (0, 1, 2) and yi = metric value on day i

  Classification:
    slope < −SLOPE_THRESHOLD → "DECLINING"
    slope > +SLOPE_THRESHOLD → "IMPROVING"
    abs(slope) <= SLOPE_THRESHOLD → "STABLE"
    < 2 data points → "INSUFFICIENT_DATA"

  Note: With only 3 data points, trends are indicative, not statistically robust.
  The meeting document notes this is an early-signal system:
  "Helps Operations decide coaching priorities and gives WFM early signals
   about attrition/disengagement." (ops_task_1.pdf §8)

Metrics tracked per agent:
  - Occupancy %       (OCC / Production)
  - Productivity %    (OCC / Present)
  - Shrinkage Rate %  (Shrinkage / Present)
  - Shift Span Hours
  - Present Hours

Data Source
-----------
  CSV: Agent_Breakdown_140426.csv  (all 3 days used together)

Endpoint
--------
  GET /api/operations/trend-analysis
"""

from datetime import date
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Query
from pydantic import BaseModel

from operations.services.csv_loader import (
    build_agent_day_aggregates,
    available_dates,
    get_rows,
)

router = APIRouter()

SLOPE_THRESHOLD = 1.0  # % per day — below this change is considered "stable"


def _linear_slope(values: List[Tuple[int, float]]) -> Optional[float]:
    """Compute linear regression slope for (day_index, value) pairs."""
    n = len(values)
    if n < 2:
        return None
    xs = [x for x, _ in values]
    ys = [y for _, y in values]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    numerator = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    denominator = sum((xs[i] - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _classify_trend(slope: Optional[float]) -> str:
    if slope is None:
        return "INSUFFICIENT_DATA"
    if slope < -SLOPE_THRESHOLD:
        return "DECLINING"
    if slope > SLOPE_THRESHOLD:
        return "IMPROVING"
    return "STABLE"


class DailyMetricPoint(BaseModel):
    work_date: date
    occupancy_pct: Optional[float]
    productivity_pct: Optional[float]
    shrinkage_rate_pct: Optional[float]
    present_hours: float


class AgentTrend(BaseModel):
    agent_id: str
    team: str
    days_present: int
    daily_data: List[DailyMetricPoint]

    # Slopes (% change per day)
    occupancy_slope: Optional[float]
    productivity_slope: Optional[float]
    shrinkage_slope: Optional[float]

    # Trend directions
    occupancy_trend: str
    productivity_trend: str
    shrinkage_trend: str

    overall_alert: str
    """CRITICAL | WARNING | WATCH | OK."""
    coaching_priority: bool
    """True if occupancy or productivity is DECLINING."""


class TrendAnalysisSummary(BaseModel):
    date_range: List[date]
    total_agents: int
    agents_declining_occupancy: int
    agents_declining_productivity: int
    agents_coaching_priority: int
    agents: List[AgentTrend]
    data_note: str


@router.get(
    "/trend-analysis",
    response_model=TrendAnalysisSummary,
    summary="Task 8 — Rolling Trend Analysis on Agent Performance",
    description=(
        "Analyses 3-day performance trends (Apr 12–14) per agent. "
        "Computes linear slope for Occupancy %, Productivity %, and Shrinkage Rate %. "
        "Flags agents with declining performance as coaching priorities for Operations."
    ),
)
def get_trend_analysis(
    agent_id: Optional[str] = Query(None, description="Filter to a single agent ID."),
):
    rows = get_rows()
    all_dates = available_dates()

    agg_all = build_agent_day_aggregates(rows, filter_agent=agent_id)

    # Group by agent
    agents_data: Dict[str, Dict[date, object]] = {}
    teams: Dict[str, str] = {}
    for (aid, d), rec in agg_all.items():
        agents_data.setdefault(aid, {})[d] = rec
        teams[aid] = rec.team

    agents_out: List[AgentTrend] = []
    for aid in sorted(agents_data.keys()):
        day_records = agents_data[aid]
        sorted_days = sorted(day_records.keys())

        daily_points: List[DailyMetricPoint] = []
        occ_series: List[Tuple[int, float]] = []
        prod_series: List[Tuple[int, float]] = []
        shrink_series: List[Tuple[int, float]] = []

        for idx, d in enumerate(sorted_days):
            rec = day_records[d]
            occ = rec.occupancy_pct
            prod = rec.productivity_pct
            shrink = rec.in_office_shrinkage_rate_pct

            daily_points.append(DailyMetricPoint(
                work_date=d,
                occupancy_pct=occ,
                productivity_pct=prod,
                shrinkage_rate_pct=shrink,
                present_hours=round(rec.present_hours, 3),
            ))
            if occ is not None:
                occ_series.append((idx, occ))
            if prod is not None:
                prod_series.append((idx, prod))
            if shrink is not None:
                shrink_series.append((idx, shrink))

        occ_slope = _linear_slope(occ_series)
        prod_slope = _linear_slope(prod_series)
        shrink_slope = _linear_slope(shrink_series)

        occ_trend = _classify_trend(occ_slope)
        prod_trend = _classify_trend(prod_slope)
        shrink_trend = _classify_trend(shrink_slope)

        # Overall alert
        declining = [t for t in (occ_trend, prod_trend) if t == "DECLINING"]
        shrink_rising = shrink_trend == "IMPROVING"  # shrinkage slope up = bad
        if len(declining) >= 2:
            alert = "CRITICAL"
        elif len(declining) == 1 or shrink_rising:
            alert = "WARNING"
        elif any(t == "DECLINING" for t in (occ_trend, prod_trend)):
            alert = "WATCH"
        else:
            alert = "OK"

        coaching = occ_trend == "DECLINING" or prod_trend == "DECLINING"

        agents_out.append(AgentTrend(
            agent_id=aid,
            team=teams.get(aid, ""),
            days_present=len(sorted_days),
            daily_data=daily_points,
            occupancy_slope=occ_slope,
            productivity_slope=prod_slope,
            shrinkage_slope=shrink_slope,
            occupancy_trend=occ_trend,
            productivity_trend=prod_trend,
            shrinkage_trend=shrink_trend,
            overall_alert=alert,
            coaching_priority=coaching,
        ))

    return TrendAnalysisSummary(
        date_range=all_dates,
        total_agents=len(agents_out),
        agents_declining_occupancy=sum(1 for a in agents_out if a.occupancy_trend == "DECLINING"),
        agents_declining_productivity=sum(1 for a in agents_out if a.productivity_trend == "DECLINING"),
        agents_coaching_priority=sum(1 for a in agents_out if a.coaching_priority),
        agents=agents_out,
        data_note=(
            "3 days of data (Apr 12–14). Trends are indicative only — "
            "linear regression with 3 points. Production use requires "
            "rolling 2-4 week window per BEST WFM §3.4."
        ),
    )
