from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import LeaveType, OverspendPolicy


class LeaveLedgerBase(BaseModel):
    leave_type: LeaveType
    approved_balance: Decimal = Field(..., ge=0)
    consumed_balance: Decimal = Field(0, ge=0)
    overspend_policy: OverspendPolicy = OverspendPolicy.UNPAID_AUTO
    cycle_start: date


class LeaveLedgerCreate(LeaveLedgerBase):
    agent_id: str


class LeaveLedgerUpdate(BaseModel):
    approved_balance: Optional[Decimal] = None
    consumed_balance: Optional[Decimal] = None
    overspend_policy: Optional[OverspendPolicy] = None
    cycle_start: Optional[date] = None


class LeaveLedgerOut(LeaveLedgerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: str
    updated_at: Optional[datetime] = None

    @computed_field
    @property
    def remaining_balance(self) -> Decimal:
        return self.approved_balance - self.consumed_balance


class LeaveAdjustment(BaseModel):
    """Used by HR to adjust balance (carryover, accrual, overspend correction)."""

    delta: Decimal = Field(..., description="+ adds to approved_balance, - decrements")
    reason: str = Field(..., min_length=1)
