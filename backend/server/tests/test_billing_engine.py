"""Golden tests for the Billing Engine — Phase 0 of the rollout plan."""

from datetime import date
from decimal import Decimal

from finance_func.app.services.billing_engine import (
    AgentRateInputs,
    HourlyInputs,
    LeaveResolution,
    compute,
    step1_classify_worked_hours,
    step3_apply_rate_multipliers,
    step6_apply_min_max,
)
from app.models.enums import DeltaReason, MinMaxStatus


def _rates(**overrides) -> AgentRateInputs:
    defaults = dict(
        agent_id="A1",
        base_hourly_rate=Decimal("250"),
        overtime_multiplier=Decimal("1.5"),
        holiday_multiplier=Decimal("2.0"),
        night_differential=Decimal("0.10"),
        min_monthly_pay=Decimal("35000"),
        max_monthly_pay=Decimal("70000"),
        weekly_contracted_hours=40,
        currency="INR",
        rate_card_version="rc-test",
    )
    defaults.update(overrides)
    return AgentRateInputs(**defaults)


def test_step1_splits_regular_and_overtime():
    h = HourlyInputs(
        agent_id="A1",
        date=date(2026, 4, 14),
        productive_minutes=Decimal("420"),
        available_minutes=Decimal("90"),
        break_minutes=Decimal("60"),
        training_minutes=Decimal("0"),
        scheduled_minutes=Decimal("480"),
        worked_minutes=Decimal("510"),
        overtime_minutes=Decimal("30"),
        is_holiday=False,
        night_minutes=Decimal("0"),
    )
    buckets = step1_classify_worked_hours(h)
    assert buckets["regular_minutes"] == Decimal("480")
    assert buckets["overtime_minutes"] == Decimal("30")
    assert buckets["holiday_minutes"] == Decimal("0")


def test_step3_holiday_collapses_regular_into_holiday():
    h = HourlyInputs(
        agent_id="A1",
        date=date(2026, 4, 14),
        productive_minutes=Decimal("0"),
        available_minutes=Decimal("0"),
        break_minutes=Decimal("0"),
        training_minutes=Decimal("0"),
        scheduled_minutes=Decimal("480"),
        worked_minutes=Decimal("480"),
        overtime_minutes=Decimal("0"),
        is_holiday=True,
        night_minutes=Decimal("0"),
    )
    buckets = step1_classify_worked_hours(h)
    components = step3_apply_rate_multipliers(buckets, _rates(), holiday_overtime_stack=False)
    assert components.regular_pay == Decimal("0")
    # 8h * 250 * 2.0 = 4000
    assert components.holiday_pay == Decimal("4000.0000")


def test_step6_floor_applied():
    monthly_pay, reason, status, alerts = step6_apply_min_max(
        Decimal("20000"), Decimal("35000"), Decimal("70000")
    )
    assert monthly_pay == Decimal("35000.0000")
    assert reason == DeltaReason.MIN_FLOOR_APPLIED
    assert status == MinMaxStatus.FLOOR_APPLIED
    assert alerts


def test_step6_cap_applied():
    monthly_pay, reason, status, _ = step6_apply_min_max(
        Decimal("90000"), Decimal("35000"), Decimal("70000")
    )
    assert monthly_pay == Decimal("70000.0000")
    assert reason == DeltaReason.MAX_CAP_APPLIED
    assert status == MinMaxStatus.CAP_APPLIED


def test_step6_within_bounds():
    monthly_pay, reason, status, alerts = step6_apply_min_max(
        Decimal("51000"), Decimal("35000"), Decimal("70000")
    )
    assert monthly_pay == Decimal("51000.0000")
    assert reason == DeltaReason.NONE
    assert status == MinMaxStatus.WITHIN_BOUNDS
    assert alerts == []


def test_section_5_2_worked_example_golden():
    """Section 5.2 worked example, computed component-by-component.

        regular_pay   = 168 x 250                 = 42,000
        overtime_pay  = 12 x 250 x 1.5            =  4,500
        holiday_pay   = 8 x 250 x 2.0             =  4,000
        night_premium = 20 x 250 x 0.10           =    500
        monthly_gross                              = 51,000
        Min/max: 35,000 < 51,000 < 70,000 -> pass through
        Final: 51,000
    """
    rates = _rates()
    regular_pay = Decimal("168") * rates.base_hourly_rate
    overtime_pay = Decimal("12") * rates.base_hourly_rate * rates.overtime_multiplier
    holiday_pay = Decimal("8") * rates.base_hourly_rate * rates.holiday_multiplier
    night_premium = Decimal("20") * rates.base_hourly_rate * rates.night_differential

    monthly_gross = regular_pay + overtime_pay + holiday_pay + night_premium
    assert monthly_gross == Decimal("51000")

    monthly_pay, reason, status, _ = step6_apply_min_max(
        monthly_gross, rates.min_monthly_pay, rates.max_monthly_pay
    )
    assert monthly_pay == Decimal("51000.0000")
    assert reason == DeltaReason.NONE
    assert status == MinMaxStatus.WITHIN_BOUNDS


def test_full_pipeline_compute_provenance_includes_inputs():
    h = HourlyInputs(
        agent_id="A1",
        date=date(2026, 4, 14),
        productive_minutes=Decimal("420"),
        available_minutes=Decimal("60"),
        break_minutes=Decimal("60"),
        training_minutes=Decimal("0"),
        scheduled_minutes=Decimal("480"),
        worked_minutes=Decimal("480"),
        overtime_minutes=Decimal("0"),
        is_holiday=False,
        night_minutes=Decimal("0"),
    )
    result = compute(
        hours=h,
        rates=_rates(),
        leave_resolution=LeaveResolution(),
        month_to_date_gross_before_today=Decimal("0"),
        days_elapsed_in_month=14,
        days_in_month=30,
    )
    # Regular: 8h * 250 = 2000
    assert result.components.regular_pay == Decimal("2000.0000")
    assert result.daily_gross == Decimal("2000.0000")
    # Provenance must carry every input — section 8 requirement
    assert result.provenance["inputs"]["scheduled_minutes"] == Decimal("480")
    assert result.provenance["rates"]["base_hourly_rate"] == Decimal("250")
    assert result.provenance["leave_resolution"]["is_absence_day"] is False
