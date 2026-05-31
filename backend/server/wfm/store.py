"""In-memory data store — replace with a database for production."""

from wfm.models import ForecastWeekRow, CoverageRow, AgentAdherenceRow, LiveKPI
from datetime import datetime

# ── Seed Forecast Data ────────────────────────────────────────────────────────

FORECAST_ROWS: list[dict] = [
    {"week":"W23","offered_volume":12500,"handled_volume":12125,"aht_seconds":320,
     "availability_rate":31.2,"in_office_shrinkage":12.0,"planned_out_office":4.0,
     "unplanned_out_office":18.0,"leavers_fte":2.0},
    {"week":"W24","offered_volume":13200,"handled_volume":12804,"aht_seconds":317,
     "availability_rate":30.8,"in_office_shrinkage":11.8,"planned_out_office":4.0,
     "unplanned_out_office":17.0,"leavers_fte":1.5},
    {"week":"W25","offered_volume":14100,"handled_volume":13677,"aht_seconds":315,
     "availability_rate":31.5,"in_office_shrinkage":12.2,"planned_out_office":4.0,
     "unplanned_out_office":19.0,"leavers_fte":3.0},
    {"week":"W26","offered_volume":13800,"handled_volume":13386,"aht_seconds":318,
     "availability_rate":31.0,"in_office_shrinkage":12.0,"planned_out_office":4.0,
     "unplanned_out_office":18.0,"leavers_fte":1.0},
    {"week":"W27","offered_volume":12900,"handled_volume":12513,"aht_seconds":320,
     "availability_rate":31.2,"in_office_shrinkage":12.5,"planned_out_office":5.0,
     "unplanned_out_office":18.0,"leavers_fte":2.0},
    {"week":"W28","offered_volume":12100,"handled_volume":11737,"aht_seconds":322,
     "availability_rate":30.9,"in_office_shrinkage":12.0,"planned_out_office":4.0,
     "unplanned_out_office":17.0,"leavers_fte":1.5},
]

# ── Seed Coverage Data ────────────────────────────────────────────────────────

COVERAGE_ROWS: list[dict] = [
    {"week":"W23","req_prod_hrs":1692,"cap_prod_hrs":1658,"coverage_rate":98,"status":"✓ OK"},
    {"week":"W24","req_prod_hrs":1810,"cap_prod_hrs":1846,"coverage_rate":102,"status":"✓ OK"},
    {"week":"W25","req_prod_hrs":1927,"cap_prod_hrs":1814,"coverage_rate":94,"status":"⚠ Below target"},
    {"week":"W26","req_prod_hrs":1874,"cap_prod_hrs":1756,"coverage_rate":94,"status":"⚠ Below target"},
    {"week":"W27","req_prod_hrs":1751,"cap_prod_hrs":1614,"coverage_rate":92,"status":"⚠ Below target"},
    {"week":"W28","req_prod_hrs":1640,"cap_prod_hrs":1558,"coverage_rate":95,"status":"⚠ Below target"},
    {"week":"W29","req_prod_hrs":1580,"cap_prod_hrs":1622,"coverage_rate":103,"status":"✓ OK"},
    {"week":"W30","req_prod_hrs":1612,"cap_prod_hrs":1680,"coverage_rate":104,"status":"✓ OK"},
]

# ── Seed Schedule Intervals ───────────────────────────────────────────────────

SCHEDULE_INTERVALS: list[dict] = [
    {"interval":"08:00","req_hc":45,"sch_hc":42,"act_hc":41},
    {"interval":"08:30","req_hc":50,"sch_hc":47,"act_hc":46},
    {"interval":"09:00","req_hc":65,"sch_hc":63,"act_hc":62},
    {"interval":"09:30","req_hc":72,"sch_hc":75,"act_hc":74},
    {"interval":"10:00","req_hc":80,"sch_hc":82,"act_hc":81},
    {"interval":"10:30","req_hc":80,"sch_hc":80,"act_hc":79},
    {"interval":"11:00","req_hc":80,"sch_hc":78,"act_hc":None},
    {"interval":"12:00","req_hc":75,"sch_hc":85,"act_hc":None},
    {"interval":"12:30","req_hc":75,"sch_hc":88,"act_hc":None},
    {"interval":"13:00","req_hc":80,"sch_hc":100,"act_hc":None},
    {"interval":"13:30","req_hc":80,"sch_hc":100,"act_hc":None},
    {"interval":"14:00","req_hc":80,"sch_hc":88,"act_hc":None},
    {"interval":"14:30","req_hc":80,"sch_hc":82,"act_hc":None},
    {"interval":"15:00","req_hc":80,"sch_hc":80,"act_hc":None},
    {"interval":"15:30","req_hc":80,"sch_hc":80,"act_hc":None},
    {"interval":"16:00","req_hc":75,"sch_hc":77,"act_hc":None},
    {"interval":"16:30","req_hc":70,"sch_hc":66,"act_hc":None},
    {"interval":"17:00","req_hc":60,"sch_hc":55,"act_hc":None},
    {"interval":"17:30","req_hc":50,"sch_hc":44,"act_hc":None},
    {"interval":"18:00","req_hc":40,"sch_hc":40,"act_hc":None},
    {"interval":"18:30","req_hc":30,"sch_hc":31,"act_hc":None},
]

# ── Seed Live KPI ─────────────────────────────────────────────────────────────

LIVE_KPI = {
    "service_level_current": 79.1,
    "service_level_cumulative": 81.4,
    "service_level_target": 80.0,
    "aht_actual": 324,
    "aht_target": 320,
    "calls_in_queue": 14,
    "avg_speed_of_answer": 28,
    "asa_target": 20,
    "available_agents": 6,
    "abandon_rate": 5.1,
}

# ── Seed Adherence ────────────────────────────────────────────────────────────

ADHERENCE_DATA: list[dict] = [
    {"agent_name":"J. Smith","scheduled_status":"On Call","actual_status":"On Call",
     "duration_minutes":None,"infraction":None},
    {"agent_name":"M. Jones","scheduled_status":"On Call","actual_status":"Break",
     "duration_minutes":7,"infraction":"Extended Break"},
    {"agent_name":"A. Lee","scheduled_status":"On Call","actual_status":"Absent",
     "duration_minutes":42,"infraction":"No Show"},
    {"agent_name":"P. Murphy","scheduled_status":"Break 10:30","actual_status":"Break",
     "duration_minutes":3,"infraction":None},
    {"agent_name":"C. OBrien","scheduled_status":"On Call","actual_status":"ACW",
     "duration_minutes":12,"infraction":"Long ACW"},
]

# ── Seed GM Stages ────────────────────────────────────────────────────────────

GM_STAGES = [
    {"label":"Pricing","offered_volume":12000,"abandon_rate":0.030,"aht_seconds":310,
     "availability_rate":0.300,"in_office_shrinkage":0.120,"unplanned_out_office":0.180,
     "planned_out_office":0.040,"price_per_transaction_hour":7.30,"direct_cost_pph":10.39},
    {"label":"Cap Plan","offered_volume":12500,"abandon_rate":0.031,"aht_seconds":320,
     "availability_rate":0.312,"in_office_shrinkage":0.120,"unplanned_out_office":0.183,
     "planned_out_office":0.040,"price_per_transaction_hour":7.30,"direct_cost_pph":10.39},
    {"label":"Actuals","offered_volume":12048,"abandon_rate":0.029,"aht_seconds":324,
     "availability_rate":0.318,"in_office_shrinkage":0.126,"unplanned_out_office":0.191,
     "planned_out_office":0.038,"price_per_transaction_hour":7.30,"direct_cost_pph":10.39},
]

# ── Action Tracker Log ────────────────────────────────────────────────────────

ACTION_LOG: list[dict] = [
    {"time":"09:15","channel":"Phone","lob":"Billing","action":"Postponed Team A Meeting","result":"SL +3%","effective":True},
    {"time":"09:45","channel":"Phone","lob":"Billing","action":"2 OT requests sent","result":"Pending","effective":None},
    {"time":"10:22","channel":"Phone","lob":"Care","action":"Chat→Phone skill swap (x3)","result":"SL +1%","effective":True},
    {"time":"10:35","channel":"Phone","lob":"Care","action":"Break postponed (x3)","result":"SL +2%","effective":True},
    {"time":"10:47","channel":"Phone","lob":"Care","action":"Meeting postponed","result":"Pending","effective":None},
]
