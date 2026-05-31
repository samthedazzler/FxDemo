"""Section 5 — The Billing Engine.

Pure computation. Consumes ONE fully-hydrated input record (hours + leaves
+ rates) and emits ONE deterministic financial output. It never queries
upstream systems mid-computation, which is the property that makes it
testable, reproducible, and replayable for audit.

Implements the strict 7-step pipeline from section 5.1:
    Step 1 - Classify worked hours
    Step 2 - Resolve leave consumption
    Step 3 - Apply rate multipliers
    Step 4 - Sum and accrue (daily_gross)
    Step 5 - Roll up to monthly window
    Step 6 - Apply min/max pay
    Step 7 - Persist and emit (handled by caller; this returns the result)
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from app.config import settings
from app.models.enums import (
    BillingStatus,
    DeltaReason,
    MinMaxStatus,
    OverspendPolicy,
)
from app.schemas.financial import PayComponents


TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def _q(x: Decimal | float | int, places: Decimal = TWO_PLACES) -> Decimal:
    if not isinstance(x, Decimal):
        x = Decimal(str(x))
    return x.quantize(places, rounding=ROUND_HALF_UP)


@dataclass
class AgentRateInputs:
    """Rate Card snapshot for the agent (section 4.1)."""

    agent_id: str
    base_hourly_rate: Decimal
    overtime_multiplier: Decimal
    holiday_multiplier: Decimal
    night_differential: Decimal
    min_monthly_pay: Decimal
    max_monthly_pay: Optional[Decimal]
    weekly_contracted_hours: int
    currency: str
    rate_card_version: str


@dataclass
class HourlyInputs:
    """Section 4.3 Hourly Breakdown Input from WFM."""

    agent_id: str
    date: date
    productive_minutes: Decimal
    available_minutes: Decimal
    break_minutes: Decimal
    training_minutes: Decimal
    scheduled_minutes: Decimal
    worked_minutes: Decimal
    overtime_minutes: Decimal
    is_holiday: bool
    night_minutes: Decimal


@dataclass
class LeaveResolution:
    """Output of Step 2 — leave consumption resolver."""

    is_absence_day: bool = False
    paid_from_balance_days: Decimal = Decimal("0")
    unpaid_days: Decimal = Decimal("0")
    leave_pay: Decimal = Decimal("0")
    billing_status: BillingStatus = BillingStatus.FINALIZED
    policy_applied: Optional[OverspendPolicy] = None
    alerts: List[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    leave_type_used: Optional[str] = None


@dataclass
class BillingResult:
    """Output of the engine for one day."""

    agent_id: str
    date: date
    regular_minutes: Decimal
    overtime_minutes: Decimal
    holiday_minutes: Decimal
    night_minutes: Decimal
    components: PayComponents
    daily_gross: Decimal
    month_to_date_gross: Decimal
    projected_monthly_gross: Decimal
    monthly_pay: Optional[Decimal]
    delta_reason: DeltaReason
    min_max_status: MinMaxStatus
    billing_status: BillingStatus
    currency: str
    alerts: List[str]
    rate_card_version: str
    provenance: Dict[str, Any]


def step1_classify_worked_hours(h: HourlyInputs) -> Dict[str, Decimal]:
    """Section 5.1 Step 1 — Classify worked hours.

        regular_minutes  = min(worked_minutes, scheduled_minutes)
        overtime_minutes = max(0, worked_minutes - scheduled_minutes)
        night_minutes    = night_minutes (already computed by WFM)
        holiday_minutes  = worked_minutes if is_holiday else 0
    """
    regular_minutes = min(h.worked_minutes, h.scheduled_minutes)
    overtime_minutes = max(Decimal("0"), h.worked_minutes - h.scheduled_minutes)
    if h.overtime_minutes and h.overtime_minutes > overtime_minutes:
        # WFM has approved OT explicitly — trust it (section 10: un-approved
        # OT computed at regular rate, so explicit OT comes pre-validated).
        overtime_minutes = h.overtime_minutes
        regular_minutes = max(Decimal("0"), h.worked_minutes - overtime_minutes)
    night_minutes = h.night_minutes
    holiday_minutes = h.worked_minutes if h.is_holiday else Decimal("0")
    return {
        "regular_minutes": regular_minutes,
        "overtime_minutes": overtime_minutes,
        "night_minutes": night_minutes,
        "holiday_minutes": holiday_minutes,
    }


def step3_apply_rate_multipliers(
    buckets: Dict[str, Decimal],
    rates: AgentRateInputs,
    holiday_overtime_stack: bool = False,
) -> PayComponents:
    """Section 5.1 Step 3 — Apply rate multipliers.

    Note: by default overtime and holiday DO NOT stack. If the day is both
    a holiday AND has overtime, the holiday rate applies to all worked
    hours that day. The behavior is configurable per geography via
    settings.holiday_overtime_stack.
    """
    rate = rates.base_hourly_rate
    regular_min = buckets["regular_minutes"]
    overtime_min = buckets["overtime_minutes"]
    night_min = buckets["night_minutes"]
    holiday_min = buckets["holiday_minutes"]

    if holiday_min > 0 and not holiday_overtime_stack:
        # Holiday rate applies to all worked hours that day.
        # Suppress regular_pay and overtime_pay; they collapse into holiday_pay.
        regular_pay = Decimal("0")
        overtime_pay = Decimal("0")
        holiday_pay = (holiday_min / Decimal(60)) * rate * rates.holiday_multiplier
    else:
        regular_pay = (regular_min / Decimal(60)) * rate
        overtime_pay = (overtime_min / Decimal(60)) * rate * rates.overtime_multiplier
        holiday_pay = (holiday_min / Decimal(60)) * rate * rates.holiday_multiplier

    night_premium = (night_min / Decimal(60)) * rate * rates.night_differential

    return PayComponents(
        regular_pay=_q(regular_pay, FOUR_PLACES),
        overtime_pay=_q(overtime_pay, FOUR_PLACES),
        holiday_pay=_q(holiday_pay, FOUR_PLACES),
        night_premium=_q(night_premium, FOUR_PLACES),
        leave_pay=Decimal("0"),
    )


def step4_sum_and_accrue(components: PayComponents) -> Decimal:
    """Section 5.1 Step 4 — Sum and accrue."""
    daily_gross = (
        components.regular_pay
        + components.overtime_pay
        + components.holiday_pay
        + components.night_premium
        + components.leave_pay
    )
    return _q(daily_gross, FOUR_PLACES)


def step6_apply_min_max(
    monthly_gross: Decimal,
    min_pay: Decimal,
    max_pay: Optional[Decimal],
) -> tuple[Decimal, DeltaReason, MinMaxStatus, List[str]]:
    """Section 5.1 Step 6 — Apply min/max pay.

    delta_reason is non-trivial: if the floor activates, the agent is being
    subsidized; if the cap activates, the agent is working uncompensated
    overtime. Both are signals Finance must surface to Operations and HR
    (section 10: Min-pay floor activations hidden from HR mitigation).
    """
    alerts: List[str] = []
    if monthly_gross < min_pay:
        return (
            _q(min_pay, FOUR_PLACES),
            DeltaReason.MIN_FLOOR_APPLIED,
            MinMaxStatus.FLOOR_APPLIED,
            [
                f"MIN_FLOOR_APPLIED: monthly_gross {monthly_gross} < min_monthly_pay {min_pay}. "
                "Agent is being subsidized — HR alert raised."
            ],
        )
    if max_pay is not None and monthly_gross > max_pay:
        return (
            _q(max_pay, FOUR_PLACES),
            DeltaReason.MAX_CAP_APPLIED,
            MinMaxStatus.CAP_APPLIED,
            [
                f"MAX_CAP_APPLIED: monthly_gross {monthly_gross} > max_monthly_pay {max_pay}. "
                "Agent working uncompensated overtime — Ops alert raised."
            ],
        )
    return _q(monthly_gross, FOUR_PLACES), DeltaReason.NONE, MinMaxStatus.WITHIN_BOUNDS, alerts


def compute(
    hours: HourlyInputs,
    rates: AgentRateInputs,
    leave_resolution: LeaveResolution,
    month_to_date_gross_before_today: Decimal,
    days_elapsed_in_month: int,
    days_in_month: int,
) -> BillingResult:
    """Run all 7 steps end-to-end for a single agent/day.

    The caller is expected to provide:
      - `hours`: section 4.3 hourly breakdown (already received from WFM)
      - `rates`: section 4.1 agent master snapshot
      - `leave_resolution`: result of `leave_service.resolve(...)` (step 2)
      - month-to-date accumulators (needed for step 5 rollup + step 6 enforcement)
    """
    alerts: List[str] = list(leave_resolution.alerts)

    # Step 1
    buckets = step1_classify_worked_hours(hours)

    # Step 2 result is already passed in as `leave_resolution`

    # Step 3
    components = step3_apply_rate_multipliers(
        buckets,
        rates,
        holiday_overtime_stack=settings.holiday_overtime_stack,
    )

    # Mix in any leave_pay from Step 2 (paid leave at base rate)
    components = PayComponents(
        regular_pay=components.regular_pay,
        overtime_pay=components.overtime_pay,
        holiday_pay=components.holiday_pay,
        night_premium=components.night_premium,
        leave_pay=_q(leave_resolution.leave_pay, FOUR_PLACES),
    )

    # Step 4
    daily_gross = step4_sum_and_accrue(components)

    # Step 5 — roll up to monthly window
    month_to_date_gross = _q(month_to_date_gross_before_today + daily_gross, FOUR_PLACES)
    if days_elapsed_in_month > 0:
        projected_monthly_gross = _q(
            (month_to_date_gross / Decimal(days_elapsed_in_month)) * Decimal(days_in_month),
            FOUR_PLACES,
        )
    else:
        projected_monthly_gross = month_to_date_gross

    # Step 6 — applied against the PROJECTED full month to give an early signal,
    # but the binding enforcement happens on the actual monthly_gross at close.
    monthly_pay, delta_reason, min_max_status, mm_alerts = step6_apply_min_max(
        projected_monthly_gross, rates.min_monthly_pay, rates.max_monthly_pay
    )
    alerts.extend(mm_alerts)

    # Step 7 — caller persists. We compute provenance here so it's deterministic.
    provenance = {
        "inputs": {
            "agent_id": hours.agent_id,
            "date": hours.date,
            "productive_minutes": hours.productive_minutes,
            "available_minutes": hours.available_minutes,
            "break_minutes": hours.break_minutes,
            "training_minutes": hours.training_minutes,
            "scheduled_minutes": hours.scheduled_minutes,
            "worked_minutes": hours.worked_minutes,
            "overtime_minutes": hours.overtime_minutes,
            "is_holiday": hours.is_holiday,
            "night_minutes": hours.night_minutes,
        },
        "rates": {
            "base_hourly_rate": rates.base_hourly_rate,
            "overtime_multiplier": rates.overtime_multiplier,
            "holiday_multiplier": rates.holiday_multiplier,
            "night_differential": rates.night_differential,
            "min_monthly_pay": rates.min_monthly_pay,
            "max_monthly_pay": rates.max_monthly_pay,
            "rate_card_version": rates.rate_card_version,
            "currency": rates.currency,
        },
        "leave_resolution": {
            "is_absence_day": leave_resolution.is_absence_day,
            "paid_from_balance_days": leave_resolution.paid_from_balance_days,
            "unpaid_days": leave_resolution.unpaid_days,
            "leave_pay": leave_resolution.leave_pay,
            "policy_applied": leave_resolution.policy_applied.value if leave_resolution.policy_applied else None,
            "billing_status": leave_resolution.billing_status.value,
            "blocked_reason": leave_resolution.blocked_reason,
            "leave_type_used": leave_resolution.leave_type_used,
        },
        "step1_buckets": {
            "regular_minutes": buckets["regular_minutes"],
            "overtime_minutes": buckets["overtime_minutes"],
            "night_minutes": buckets["night_minutes"],
            "holiday_minutes": buckets["holiday_minutes"],
        },
        "settings": {
            "holiday_overtime_stack": settings.holiday_overtime_stack,
        },
    }

    return BillingResult(
        agent_id=hours.agent_id,
        date=hours.date,
        regular_minutes=_q(buckets["regular_minutes"], TWO_PLACES),
        overtime_minutes=_q(buckets["overtime_minutes"], TWO_PLACES),
        holiday_minutes=_q(buckets["holiday_minutes"], TWO_PLACES),
        night_minutes=_q(buckets["night_minutes"], TWO_PLACES),
        components=components,
        daily_gross=daily_gross,
        month_to_date_gross=month_to_date_gross,
        projected_monthly_gross=projected_monthly_gross,
        monthly_pay=monthly_pay,
        delta_reason=delta_reason,
        min_max_status=min_max_status,
        billing_status=leave_resolution.billing_status,
        currency=rates.currency,
        alerts=alerts,
        rate_card_version=rates.rate_card_version,
        provenance=provenance,
    )
