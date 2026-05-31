from fastapi import APIRouter
from wfm.models import RTMActionRequest
from wfm.store import LIVE_KPI, ADHERENCE_DATA, ACTION_LOG

router = APIRouter()

RTM_ACTION_MATRIX = {
    "WHITE": {
        "condition": "> 85% for 2 consecutive intervals",
        "actions": ["Initiate VTO collection", "Request increase in non-production activities"],
        "communication": "RTA → Supervisor → CE",
    },
    "GREEN": {
        "condition": "80%–85%",
        "actions": ["Monitor closely", "Log in action tracker", "Refuse additional shrinkage requests"],
        "communication": "RTA monitors",
    },
    "AMBER": {
        "condition": "75%–80% for 2 consecutive intervals",
        "actions": ["Prioritise lower-SL queues", "Dedicate multiskill CEs to queue",
                    "Refuse new shrinkage", "Alert Supervisor on duty"],
        "communication": "RTA → Supervisor → CE | OM informed",
    },
    "RED": {
        "condition": "< 75% in 1 interval",
        "actions": ["Cancel all non-essential shrinkage", "Redistribute breaks immediately",
                    "Collect OT", "Change skill priorities in ACD", "Escalate to OM + Client"],
        "communication": "RTA → CE directly | RTA → Supervisor → CE | OM → Client if contractual",
    },
}

def _sl_status(sl: float) -> str:
    if sl > 85:   return "WHITE"
    if sl >= 80:  return "GREEN"
    if sl >= 75:  return "AMBER"
    return "RED"

@router.get("/live-kpis")
def get_live_kpis():
    """Return current live KPI snapshot."""
    kpi    = LIVE_KPI.copy()
    status = _sl_status(kpi["service_level_current"])
    kpi["sl_status"]        = status
    kpi["recommended_actions"] = RTM_ACTION_MATRIX[status]["actions"]
    kpi["communication_flow"]  = RTM_ACTION_MATRIX[status]["communication"]
    return kpi

@router.get("/action-matrix")
def get_action_matrix():
    return RTM_ACTION_MATRIX

@router.post("/action-matrix/recommend")
def recommend_action(payload: RTMActionRequest):
    """Given a live service level, return the correct action matrix tier."""
    status = _sl_status(payload.service_level)
    return {
        "service_level": payload.service_level,
        "status": status,
        **RTM_ACTION_MATRIX[status],
    }

@router.get("/adherence")
def get_adherence():
    return {
        "agents": ADHERENCE_DATA,
        "summary": {
            "total_active": 48, "on_call": 39, "on_break": 4,
            "in_training": 3, "absent": 2,
        }
    }

@router.get("/action-log")
def get_action_log():
    return {"log": ACTION_LOG}

@router.post("/action-log")
def add_action_log(entry: dict):
    ACTION_LOG.append(entry)
    return {"status": "logged", "total_entries": len(ACTION_LOG)}

@router.get("/interval-projection")
def get_interval_projection():
    return {"eod_projection": {
        "service_level": 79.8,
        "abandon_rate": 5.1,
        "threshold_sl": 80.0,
        "at_risk": True,
        "recommendation": "Postpone 2 team meetings",
    }, "intervals": [
        {"interval":"11:00","req":80,"sch":78,"proj":76,"sl_impact":-2},
        {"interval":"11:30","req":80,"sch":78,"proj":77,"sl_impact":-2},
        {"interval":"12:00","req":75,"sch":88,"proj":87,"sl_impact":+1},
        {"interval":"13:00","req":80,"sch":100,"proj":98,"sl_impact":+3},
        {"interval":"14:00","req":80,"sch":88,"proj":85,"sl_impact":0},
        {"interval":"15:00","req":80,"sch":80,"proj":80,"sl_impact":0},
    ]}
