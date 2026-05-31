from fastapi import APIRouter
from wfm.models import ScheduleAnalysisRequest, ScheduleAnalysisResult, ScheduleSummary, IntervalStatus
from wfm.store import SCHEDULE_INTERVALS
from typing import List
router = APIRouter()
THRESHOLD_LOW  = 85.0
THRESHOLD_HIGH = 115.0
def _classify_interval(coverage: float) -> tuple[IntervalStatus, str]:
    if coverage > THRESHOLD_HIGH:
        return IntervalStatus.over,  "Offer VTO"
    elif coverage >= 100.0:
        return IntervalStatus.green, "—"
    elif coverage >= 95.0:
        return IntervalStatus.green, "—"
    elif coverage >= THRESHOLD_LOW:
        return IntervalStatus.amber, "Check OT"
    else:
        return IntervalStatus.red,   "Request OT immediately"
def analyse_intervals(intervals: list) -> tuple[List[ScheduleAnalysisResult], ScheduleSummary]:
    results = []
    within  = 0
    over_hc = under_hc = total_req = total_sch = 0
    for iv in intervals:
        req = iv["req_hc"]; sch = iv["sch_hc"]
        act = iv.get("act_hc")
        gap = sch - req
        cov = (sch / req * 100) if req else 0
        status, action = _classify_interval(cov)
        if THRESHOLD_LOW <= cov <= THRESHOLD_HIGH:
            within += 1
        if gap > 0:
            over_hc  += gap
        else:
            under_hc += abs(gap)
        total_req += req
        total_sch += sch
        results.append(ScheduleAnalysisResult(
            interval=iv["interval"], req_hc=req, sch_hc=sch, act_hc=act,
            gap=gap, coverage_rate=round(cov, 1), status=status, ai_action=action,
        ))
    total    = len(intervals)
    eff      = round(within / total * 100, 1) if total else 0
    over_pct = round(over_hc  / total_req * 100, 1) if total_req else 0
    und_pct  = round(under_hc / total_req * 100, 1) if total_req else 0
    summary = ScheduleSummary(
        scheduling_efficiency=eff,
        over_scheduling_pct=over_pct,
        under_scheduling_pct=und_pct,
        total_req=total_req,
        total_sch=total_sch,
    )
    return results, summary
@router.get("/intervals")
def get_intervals():
    """Return seeded interval coverage table with analysis."""
    results, summary = analyse_intervals(SCHEDULE_INTERVALS)
    return {
        "week": "W23", "date": "23 Jun 2026", "lob": "Customer Care",
        "intervals": [r.dict() for r in results],
        "summary": summary.dict(),
        "target_efficiency": 75.0,
    }
@router.post("/analyse")
def analyse_schedule(payload: ScheduleAnalysisRequest):
    """Analyse a custom interval table submitted by the user."""
    raw = [iv.dict() for iv in payload.intervals]
    results, summary = analyse_intervals(raw)
    return {
        "week": payload.week, "date": payload.date, "lob": payload.lob,
        "intervals": [r.dict() for r in results],
        "summary": summary.dict(),
        "target_efficiency": 75.0,
    }
@router.get("/metrics")
def get_schedule_metrics():
    return {"metrics": [
        {"metric":"Scheduling Efficiency",          "result":"87.2%","target":"≥75%","status":"✓"},
        {"metric":"Over-scheduling %",              "result":"+5.3%","target":"Minimise","status":"⚠"},
        {"metric":"Under-scheduling %",             "result":"-2.1%","target":"Minimise","status":"✓"},
        {"metric":"Preference Fulfillment Rate",    "result":"83.4%","target":"≥80%","status":"✓"},
        {"metric":"Availability Compliance Rate",   "result":"100%", "target":"100%","status":"✓"},
        {"metric":"Legal Violations",               "result":"0",    "target":"0",   "status":"✓"},
        {"metric":"Shift Swap Approval Rate",       "result":"91.2%","target":"≥85%","status":"✓"},
        {"metric":"Weekly Schedule Change Rate",    "result":"4.1%", "target":"<5%", "status":"✓"},
        {"metric":"Supervisor Coverage ≥80% of CE","result":"81.3%","target":"≥80%","status":"✓"},
    ]}