from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ReconciliationCheckType


class ReconciliationFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_date: date
    check_type: ReconciliationCheckType
    agent_id: Optional[str] = None
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class ReconciliationRunResult(BaseModel):
    """Section 6.4 — output of the nightly Reconciliation Service run."""

    run_date: date
    coverage_findings: int
    leave_integrity_findings: int
    preview_vs_actual_findings: int
    total_findings: int
    findings: List[ReconciliationFindingOut]
