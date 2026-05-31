from fastapi import APIRouter
from wfm.models import GMStageData, GMResult, WhatIfRequest
from wfm.store import GM_STAGES
from typing import List

router = APIRouter()

def _compute_gm(s: GMStageData) -> GMResult:
    handled    = s.offered_volume * (1 - s.abandon_rate)
    tx_hrs     = handled * s.aht_seconds / 3600
    prod_hrs   = tx_hrs / (1 - s.availability_rate)
    present    = prod_hrs / (1 - s.in_office_shrinkage)
    sch_net    = present / (1 - s.unplanned_out_office)
    sch_gross  = sch_net / (1 - s.planned_out_office)

    revenue    = tx_hrs * s.price_per_transaction_hour
    costs      = present * s.direct_cost_pph
    gm_eur     = revenue - costs
    gm_pct     = (gm_eur / revenue * 100) if revenue else 0

    return GMResult(
        label=s.label,
        handled_volume=round(handled, 0),
        transaction_hours=round(tx_hrs, 1),
        production_hours=round(prod_hrs, 1),
        present_hours=round(present, 1),
        scheduled_hours_gross=round(sch_gross, 1),
        revenue=round(revenue, 2),
        direct_costs=round(costs, 2),
        gross_margin_eur=round(gm_eur, 2),
        gross_margin_pct=round(gm_pct, 2),
    )

@router.get("/stages")
def get_gm_stages():
    """Return GM calculation for all seeded stages (Pricing, Cap Plan, Actuals)."""
    results = [_compute_gm(GMStageData(**s)) for s in GM_STAGES]
    return {"stages": [r.dict() for r in results]}

@router.post("/calculate")
def calculate_gm(payload: GMStageData):
    return _compute_gm(payload).dict()

@router.post("/what-if")
def what_if(payload: WhatIfRequest):
    """Run baseline vs two scenarios vs combined."""
    base = payload.baseline

    def _scenario(label, aht_delta=0.0, shrink_delta=0.0) -> dict:
        s = GMStageData(
            label=label,
            offered_volume=base.offered_volume,
            abandon_rate=base.abandon_rate,
            aht_seconds=base.aht_seconds + aht_delta,
            availability_rate=base.availability_rate,
            in_office_shrinkage=max(0, base.in_office_shrinkage + shrink_delta),
            unplanned_out_office=base.unplanned_out_office,
            planned_out_office=base.planned_out_office,
            price_per_transaction_hour=base.price_per_transaction_hour,
            direct_cost_pph=base.direct_cost_pph,
        )
        return _compute_gm(s).dict()

    baseline_result = _scenario("Baseline")
    scenario_a      = _scenario("Scenario A (AHT reduction)",
                                aht_delta=payload.aht_delta_seconds)
    scenario_b      = _scenario("Scenario B (Shrinkage reduction)",
                                shrink_delta=payload.in_office_shrinkage_delta)
    scenario_c      = _scenario("Scenario C (A + B)",
                                aht_delta=payload.aht_delta_seconds,
                                shrink_delta=payload.in_office_shrinkage_delta)

    base_gm = baseline_result["gross_margin_pct"]
    for sc in [scenario_a, scenario_b, scenario_c]:
        sc["gm_improvement_pp"] = round(sc["gross_margin_pct"] - base_gm, 2)
        weekly_delta = sc["gross_margin_eur"] - baseline_result["gross_margin_eur"]
        sc["weekly_gm_delta_eur"]    = round(weekly_delta, 2)
        sc["annualised_gm_delta_eur"] = round(weekly_delta * 52, 2)

    return {
        "baseline": baseline_result,
        "scenario_a": scenario_a,
        "scenario_b": scenario_b,
        "scenario_c": scenario_c,
    }

@router.get("/audit-scores")
def get_audit_scores():
    return {"scores": [
        {"area":"Forecasting Process",      "score":90,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"Capacity Planning",        "score":88,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"Scheduling Process",       "score":82,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"Real-Time Management",     "score":85,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"Routing & Skills Mgmt",    "score":80,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"Vacation Planning",        "score":76,"target":80,"status":"⚠ Below","corrective_action":"Global tool deployment pending — interim manual process gap to be closed by Q3"},
        {"area":"GM Estimation",            "score":83,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"Reports and Analysis",     "score":88,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"WFM Team Structure",       "score":85,"target":80,"status":"✓ OK","corrective_action":"—"},
        {"area":"Meetings Cadence",         "score":79,"target":80,"status":"⚠ Below","corrective_action":"RTM routine dropped to 3x/week — return to daily cadence immediately"},
        {"area":"Governance & Compliance",  "score":86,"target":80,"status":"✓ OK","corrective_action":"—"},
    ]}