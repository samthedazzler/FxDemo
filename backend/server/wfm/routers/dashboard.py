from fastapi import APIRouter
from wfm.store import COVERAGE_ROWS, LIVE_KPI, FORECAST_ROWS

router = APIRouter()

@router.get("/kpis")
def get_dashboard_kpis():
    """Return top-level WFM health indicator cards."""
    return {
        "req_coverage_rate": 98.4,
        "scheduling_efficiency": 91.2,
        "adherence_rate": 95.8,
        "forecast_accuracy": 87.3,
        "occupancy": 78.4,
        "in_office_shrinkage": 12.6,
        "annualised_attrition": 8.1,
        "gm_estimate": 34.8,
        "targets": {
            "req_coverage_rate": 100,
            "scheduling_efficiency": 75,
            "adherence_rate": 95,
            "forecast_accuracy": 85,
            "occupancy_max": 85,
            "gm_estimate": 35,
        },
        "ai_recommendations": [
            {
                "id": "rec_001",
                "severity": "warning",
                "message": "W26 coverage projected at 93.2%",
                "action": "Recommend opening 4 hires now",
            },
            {
                "id": "rec_002",
                "severity": "warning",
                "message": "Attrition in LOB-2 rising",
                "action": "3 CEs flagged pre-leave pattern",
            },
        ],
        "cross_department": {
            "operations": {"sl_today": 81.2, "sl_target": 80.0, "aht_actual": 318, "aht_estimate": 320},
            "finance":    {"direct_cost_pph": 10.39, "gm_gap_pp": -0.2},
            "recruitment":{"pending_approvals": 4, "w26_nht_confirmed": True},
        }
    }

@router.get("/coverage-trend")
def get_coverage_trend():
    """6-month rolling coverage trend data for chart."""
    return {"data": COVERAGE_ROWS}

@router.get("/live-feed")
def get_live_feed():
    """Cross-department live feed snapshot."""
    return LIVE_KPI
