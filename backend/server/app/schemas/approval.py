from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LeaveType


class PendingApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: str
    date: date
    leave_type: Optional[LeaveType] = None
    reason: str
    status: str
    manager_id: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime


class ApprovalDecisionRequest(BaseModel):
    """Section 6.3 — MANAGER_APPROVAL decision input."""

    manager_id: str = Field(..., min_length=1)
    decision: str = Field(..., pattern="^(APPROVE|DENY)$")
    note: Optional[str] = None
