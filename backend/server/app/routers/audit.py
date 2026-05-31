"""Section 8 — Auditability & Compliance endpoints.

Read-only audit log. Every Billing Engine computation, correction, override,
manager decision, and leave adjustment leaves a record here. This is the
trail used to defend payroll, statutory, and client billing disputes."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import AuditLog

router = APIRouter(prefix="/audit", tags=["Audit"])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: Optional[str] = None
    event_type: str
    target_id: Optional[str] = None
    content_hash: Optional[str] = None
    parent_hash: Optional[str] = None
    payload: Dict[str, Any]
    actor: str
    created_at: datetime


@router.get("/log", response_model=List[AuditLogOut])
def list_audit(
    agent_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if agent_id is not None:
        q = q.filter(AuditLog.agent_id == agent_id)
    if event_type is not None:
        q = q.filter(AuditLog.event_type == event_type)
    return q.order_by(AuditLog.created_at.desc()).limit(limit).all()
