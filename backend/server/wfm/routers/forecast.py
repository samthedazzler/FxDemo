from fastapi import APIRouter, HTTPException
from wfm.models import ForecastCreateRequest, ForecastWeekRow
from wfm.store import FORECAST_ROWS
from typing import List

router = APIRouter()

@router.get("/rows")
def get_forecast_rows():
    """Return the locked forecast assumption table."""
    return {"forecast_type": "Locked (Binding)", "period": "Jun–Nov 2026", "rows": FORECAST_ROWS}

@router.post("/rows")
def create_forecast(payload: ForecastCreateRequest):
    """Save a new forecast version."""
    FORECAST_ROWS.clear()
    for row in payload.rows:
        FORECAST_ROWS.append(row.dict())
    return {"status": "saved", "rows_saved": len(FORECAST_ROWS)}

@router.put("/rows/{week}")
def update_forecast_row(week: str, row: ForecastWeekRow):
    """Update a single week row in the forecast."""
    for i, r in enumerate(FORECAST_ROWS):
        if r["week"] == week:
            FORECAST_ROWS[i] = row.dict()
            return {"status": "updated", "week": week}
    raise HTTPException(status_code=404, detail=f"Week {week} not found")

@router.get("/version-comparison")
def get_version_comparison():
    """Forecast version comparison — client locked vs internal vs actuals."""
    return {
        "metric": "Offered Volume",
        "versions": [
            {"label": "Client Locked Forecast",     "W23": 12500, "W24": 13200, "W25": 14100, "W26": 13800},
            {"label": "Previous Internal Forecast",  "W23": 12200, "W24": 12950, "W25": 13800, "W26": 13500},
            {"label": "Current Internal Forecast",   "W23": 12125, "W24": 12804, "W25": 13677, "W26": 13386},
            {"label": "Actuals",                     "W23": 12048, "W24": 12711, "W25": None,  "W26": None},
        ],
        "fca": {
            "client":   {"W23": 90.4, "W24": 87.3},
            "internal": {"W23": 96.2, "W24": 96.2},
        },
        "ai_recommendation": "Client forecast running +3.8% above actuals. Recommend internally agreed forecast at -4% vs client locked for W26+.",
    }

@router.get("/events")
def get_event_register():
    return {"events": [
        {"event":"Summer Bank Holiday","type":"Holiday","start":"04-Aug","end":"04-Aug","impact_pct":-35,"applied_to":"W32"},
        {"event":"Product Launch",     "type":"Client", "start":"12-Jun","end":"18-Jun","impact_pct":+22,"applied_to":"W24"},
        {"event":"Payment Cycle Peak", "type":"Recurring","start":"20th/mth","end":"22nd/mth","impact_pct":+18,"applied_to":"Monthly"},
        {"event":"Black Friday",       "type":"Seasonal","start":"27-Nov","end":"01-Dec","impact_pct":+45,"applied_to":"W48"},
    ]}
