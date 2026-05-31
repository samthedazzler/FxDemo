from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

# ── Enums ────────────────────────────────────────────────────────────────────

class ForecastType(str, Enum):
    long_term   = "Long-Term (Indicative)"
    guidance    = "Guidance (Indicative)"
    locked      = "Locked (Binding)"
    agreed      = "Internally Agreed"
    advisory    = "Advisory"

class IntervalStatus(str, Enum):
    white = "WHITE"
    green = "GREEN"
    amber = "AMBER"
    red   = "RED"
    over  = "OVER"

# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardKPI(BaseModel):
    req_coverage_rate: float        # %
    scheduling_efficiency: float    # %
    adherence_rate: float           # %
    forecast_accuracy: float        # %
    occupancy: float                # %
    in_office_shrinkage: float      # %
    annualised_attrition: float     # %
    gm_estimate: float              # %

# ── Forecast ──────────────────────────────────────────────────────────────────

class ForecastWeekRow(BaseModel):
    week: str
    offered_volume: int
    handled_volume: int
    aht_seconds: int
    availability_rate: float        # %
    in_office_shrinkage: float      # %
    planned_out_office: float       # %
    unplanned_out_office: float     # %
    leavers_fte: float

class ForecastCreateRequest(BaseModel):
    forecast_type: ForecastType
    period: str
    lob: str = "All"
    channel: str = "Phone"
    rows: List[ForecastWeekRow]

# ── Capacity ──────────────────────────────────────────────────────────────────

class RequirementBuildRequest(BaseModel):
    week: str
    offered_volume: int
    abandon_rate: float             # decimal e.g. 0.031
    aht_seconds: int
    availability_rate: float        # decimal e.g. 0.312
    in_office_shrinkage: float      # decimal
    unplanned_out_office: float     # decimal
    planned_out_office: float       # decimal
    hours_per_week: float = 40.0

class RequirementBuildResult(BaseModel):
    week: str
    offered_volume: int
    handled_volume: float
    transaction_hours: float
    production_hours: float
    present_hours: float
    scheduled_hours_net: float
    scheduled_hours_gross: float
    fte_requirement: float

class CapacityBuildRequest(BaseModel):
    week: str
    current_fte: float
    leavers: float
    new_hires: float
    transfers: float
    planned_out_office: float
    unplanned_out_office: float
    in_office_shrinkage: float
    availability_rate: float
    aht_seconds: int
    abandon_rate: float
    hours_per_week: float = 40.0

class CapacityBuildResult(BaseModel):
    week: str
    net_fte: float
    scheduled_hours_gross: float
    scheduled_hours_net: float
    present_hours: float
    production_hours: float
    transaction_hours: float
    handled_volume: float
    offered_volume: float

class CoverageRow(BaseModel):
    week: str
    req_prod_hrs: float
    cap_prod_hrs: float
    coverage_rate: float
    status: str

# ── Schedule ──────────────────────────────────────────────────────────────────

class IntervalRow(BaseModel):
    interval: str
    req_hc: int
    sch_hc: int
    act_hc: Optional[int] = None

class ScheduleAnalysisResult(BaseModel):
    interval: str
    req_hc: int
    sch_hc: int
    act_hc: Optional[int]
    gap: int
    coverage_rate: float
    status: IntervalStatus
    ai_action: str

class ScheduleAnalysisRequest(BaseModel):
    week: str
    date: str
    lob: str
    intervals: List[IntervalRow]

class ScheduleSummary(BaseModel):
    scheduling_efficiency: float
    over_scheduling_pct: float
    under_scheduling_pct: float
    total_req: int
    total_sch: int

# ── RTM ───────────────────────────────────────────────────────────────────────

class LiveKPI(BaseModel):
    service_level_current: float
    service_level_cumulative: float
    service_level_target: float = 80.0
    aht_actual: int
    aht_target: int
    calls_in_queue: int
    avg_speed_of_answer: int
    asa_target: int = 20
    available_agents: int
    abandon_rate: float

class RTMActionRequest(BaseModel):
    service_level: float

class AgentAdherenceRow(BaseModel):
    agent_name: str
    scheduled_status: str
    actual_status: str
    duration_minutes: Optional[int] = None
    infraction: Optional[str] = None

# ── Erlang ────────────────────────────────────────────────────────────────────

class ErlangCRequest(BaseModel):
    calls_per_interval: int
    aht_seconds: int
    interval_minutes: int = 30
    service_level_target: float = 0.80   # 80%
    service_time_target_seconds: int = 20

class ErlangCResult(BaseModel):
    agents_required: int
    traffic_intensity_erlangs: float
    occupancy: float
    prob_waiting: float
    avg_speed_of_answer: float
    sensitivity: List[dict]

class ErlangBRequest(BaseModel):
    busy_hour_traffic_erlangs: float
    target_blocking_pct: float = 1.0    # %

class ErlangBResult(BaseModel):
    trunks_required: int
    actual_blocking_pct: float
    traffic_per_trunk: float
    utilisation: float
    sensitivity: List[dict]

# ── GM Estimator ──────────────────────────────────────────────────────────────

class GMStageData(BaseModel):
    label: str
    offered_volume: int
    abandon_rate: float
    aht_seconds: int
    availability_rate: float
    in_office_shrinkage: float
    unplanned_out_office: float
    planned_out_office: float
    price_per_transaction_hour: float
    direct_cost_pph: float

class GMResult(BaseModel):
    label: str
    handled_volume: float
    transaction_hours: float
    production_hours: float
    present_hours: float
    scheduled_hours_gross: float
    revenue: float
    direct_costs: float
    gross_margin_eur: float
    gross_margin_pct: float

class WhatIfRequest(BaseModel):
    baseline: GMStageData
    aht_delta_seconds: float = 0.0
    in_office_shrinkage_delta: float = 0.0
