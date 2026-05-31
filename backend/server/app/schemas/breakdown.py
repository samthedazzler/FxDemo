from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict

from pydantic import BaseModel, ConfigDict, Field


class StatusBreakdownItem(BaseModel):
    """One line of source_status_breakdown for audit (section 7.1)."""

    status: str
    minutes: Decimal


class HourlyBreakdownIn(BaseModel):
    """Section 4.3 + Section 7.1 — payload that WFM publishes per agent per day.

    Matches the contract:
      POST /finance/breakdown
      { agent_id, date, scheduled_minutes, worked_minutes, overtime_minutes,
        productive_minutes, available_minutes, break_minutes, training_minutes,
        is_holiday, night_minutes, source_status_breakdown }
    """

    agent_id: str
    date: date
    productive_minutes: Decimal = Field(0, ge=0)
    available_minutes: Decimal = Field(0, ge=0)
    break_minutes: Decimal = Field(0, ge=0)
    training_minutes: Decimal = Field(0, ge=0)
    scheduled_minutes: Decimal = Field(0, ge=0)
    worked_minutes: Decimal = Field(0, ge=0)
    overtime_minutes: Decimal = Field(0, ge=0)
    is_holiday: bool = False
    night_minutes: Decimal = Field(0, ge=0)
    source_status_breakdown: Optional[Dict[str, float]] = None
    site: Optional[str] = None


class HourlyBreakdownOut(HourlyBreakdownIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    received_at: datetime


class WFMRawAggregateRequest(BaseModel):
    """Used by WFM Aggregator to convert raw status rows into a daily breakdown
    using the Appendix Status -> Pay Category mapping (section 11)."""

    agent_id: str
    date: date
    scheduled_minutes: Decimal = Field(0, ge=0)
    is_holiday: bool = False
    site: Optional[str] = None
    status_minutes: Dict[str, float] = Field(
        ..., description="Map of WFM Status -> total minutes for the day"
    )
    night_minutes: Decimal = Field(0, ge=0, description="Minutes worked between 22:00-06:00")
