from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Any, Dict

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DeltaReason, MinMaxStatus, BillingStatus


class PayComponents(BaseModel):
    regular_pay: Decimal
    overtime_pay: Decimal
    holiday_pay: Decimal
    night_premium: Decimal
    leave_pay: Decimal = Decimal("0")


class FinancialBreakdownOut(BaseModel):
    """Section 7.2 — What Finance publishes back on each /finance/breakdown."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: str
    date: date
    daily_gross: Decimal
    components: PayComponents
    month_to_date_gross: Decimal
    projected_monthly_gross: Decimal
    monthly_pay: Optional[Decimal] = None
    min_max_status: MinMaxStatus
    delta_reason: DeltaReason
    billing_status: BillingStatus
    currency: str
    content_hash: str
    parent_id: Optional[int] = None
    rate_card_version: Optional[str] = None
    provenance: Dict[str, Any]
    alerts: List[str] = []
    created_at: datetime


class BillingResponse(BaseModel):
    """The literal response shape from section 7.2 of the design doc."""

    agent_id: str
    date: date
    daily_gross: Decimal
    components: PayComponents
    month_to_date_gross: Decimal
    projected_monthly_gross: Decimal
    min_max_status: MinMaxStatus
    delta_reason: DeltaReason
    billing_status: BillingStatus
    alerts: List[str] = []
    content_hash: str
    rate_card_version: Optional[str] = None


class MonthlyRollup(BaseModel):
    """Section 5.1 step 5 + step 6 — monthly window with min/max enforcement."""

    agent_id: str
    year: int
    month: int
    monthly_gross: Decimal
    monthly_pay: Decimal
    min_monthly_pay: Decimal
    max_monthly_pay: Optional[Decimal]
    delta_reason: DeltaReason
    min_max_status: MinMaxStatus
    days_counted: int
    breakdown_by_component: PayComponents
    alerts: List[str] = []
