from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class OvertimePreviewRequest(BaseModel):
    """Section 7.3 — Operations cost-preview endpoint."""

    agent_id: str
    proposed_overtime_hours: Decimal = Field(..., ge=0)
    date: date
    is_holiday: bool = False
    night_hours: Decimal = Field(0, ge=0)


class OvertimePreviewResponse(BaseModel):
    """Section 7.3 — what Finance returns synchronously to the WFM dashboard."""

    agent_id: str
    date: date
    estimated_additional_cost: Decimal
    agent_month_to_date: Decimal
    projected_after_overtime: Decimal
    cap_breach: bool
    floor_active: bool
    approval_recommendation: str
    rate_card_version: str
    stale_rate_card: bool = False
    notes: list[str] = []
