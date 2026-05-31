from fastapi import APIRouter
from wfm.models import RequirementBuildRequest, RequirementBuildResult, CapacityBuildRequest, CapacityBuildResult
from wfm.store import COVERAGE_ROWS
router = APIRouter()
def _hourly_breakdown_requirement(r: RequirementBuildRequest) -> RequirementBuildResult:
    handled     = r.offered_volume * (1 - r.abandon_rate)
    tx_hrs      = handled * r.aht_seconds / 3600
    prod_hrs    = tx_hrs / (1 - r.availability_rate)
    present_hrs = prod_hrs / (1 - r.in_office_shrinkage)
    sch_net     = present_hrs / (1 - r.unplanned_out_office)
    sch_gross   = sch_net / (1 - r.planned_out_office)
    fte         = sch_gross / r.hours_per_week
    return RequirementBuildResult(
        week=r.week,
        offered_volume=r.offered_volume,
        handled_volume=round(handled, 1),
        transaction_hours=round(tx_hrs, 1),
        production_hours=round(prod_hrs, 1),
        present_hours=round(present_hrs, 1),
        scheduled_hours_net=round(sch_net, 1),
        scheduled_hours_gross=round(sch_gross, 1),
        fte_requirement=round(fte, 1),
    )
def _hourly_breakdown_capacity(r: CapacityBuildRequest) -> CapacityBuildResult:
    net_fte     = r.current_fte - r.leavers + r.new_hires + r.transfers
    sch_gross   = net_fte * r.hours_per_week
    sch_net     = sch_gross * (1 - r.planned_out_office)
    present_hrs = sch_net   * (1 - r.unplanned_out_office)
    prod_hrs    = present_hrs * (1 - r.in_office_shrinkage)
    tx_hrs      = prod_hrs  * (1 - r.availability_rate)
    handled     = tx_hrs / (r.aht_seconds / 3600)
    offered     = handled / (1 - r.abandon_rate)
    return CapacityBuildResult(
        week=r.week,
        net_fte=round(net_fte, 1),
        scheduled_hours_gross=round(sch_gross, 1),
        scheduled_hours_net=round(sch_net, 1),
        present_hours=round(present_hrs, 1),
        production_hours=round(prod_hrs, 1),
        transaction_hours=round(tx_hrs, 1),
        handled_volume=round(handled, 0),
        offered_volume=round(offered, 0),
    )
@router.post("/requirement-build", response_model=RequirementBuildResult)
def build_requirement(payload: RequirementBuildRequest):
    """Run the full hourly breakdown model downward — volume to FTE requirement."""
    return _hourly_breakdown_requirement(payload)
@router.post("/capacity-build", response_model=CapacityBuildResult)
def build_capacity(payload: CapacityBuildRequest):
    """Run the full hourly breakdown model upward — FTE to volume capacity."""
    return _hourly_breakdown_capacity(payload)
@router.post("/coverage-rate")
def calculate_coverage(req: RequirementBuildRequest, cap: CapacityBuildRequest):
    """Calculate requirement coverage rate = Cap Prod Hrs ÷ Req Prod Hrs."""
    r = _hourly_breakdown_requirement(req)
    c = _hourly_breakdown_capacity(cap)
    rate = (c.production_hours / r.production_hours) * 100 if r.production_hours else 0
    status = "✓ OK" if rate >= 100 else ("⚠ Below target" if rate >= 90 else "🔴 Critical")
    return {
        "week": req.week,
        "req_production_hours": r.production_hours,
        "cap_production_hours": c.production_hours,
        "coverage_rate_pct": round(rate, 1),
        "status": status,
        "ai_flag": rate < 95,
    }
@router.get("/coverage-dashboard")
def get_coverage_dashboard():
    """Return the 6-month rolling coverage dashboard from seed data."""
    return {
        "data": COVERAGE_ROWS,
        "ai_alert": "W25–W28 below 95% — recommend opening 6 hire requisitions by 26-May to enter production W27."
    }
@router.get("/recruitment-tracker")
def get_recruitment_tracker():
    return {"tracker": [
        {"week_need":"W27","fte_need":6,"hire_date":"W24","nht_start":"W24","nesting":"W26","prod_entry":"W27","pass_rate":85,"net_fte":4.1},
        {"week_need":"W28","fte_need":4,"hire_date":"W25","nht_start":"W25","nesting":"W27","prod_entry":"W28","pass_rate":85,"net_fte":3.4},
        {"week_need":"W29","fte_need":3,"hire_date":"W26","nht_start":"W26","nesting":"W28","prod_entry":"W29","pass_rate":85,"net_fte":1.6},
    ]}
@router.get("/leavers-tracker")
def get_leavers_tracker():
    return {"leavers": [
        {"week":"W21","forecast":1,"actuals":2,"projection":2},
        {"week":"W22","forecast":2,"actuals":1,"projection":1},
        {"week":"W23","forecast":2,"actuals":2,"projection":2},
        {"week":"W24","forecast":3,"actuals":5,"projection":5,"alert":True},
        {"week":"W25","forecast":3,"actuals":None,"projection":5,"alert":True},
        {"week":"W26","forecast":2,"actuals":None,"projection":2},
    ]}