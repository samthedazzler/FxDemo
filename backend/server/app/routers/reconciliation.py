"""Section 6.4 — Daily Reconciliation endpoints + section 6.3 pending queue."""

from datetime import date as ddate
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import PendingApproval, ReconciliationFinding
from app.models.enums import ReconciliationCheckType
from app.schemas.approval import ApprovalDecisionRequest, PendingApprovalOut
from app.schemas.reconciliation import ReconciliationFindingOut, ReconciliationRunResult
from app.services import leave_service, reconciliation_service, audit

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post("/run", response_model=ReconciliationRunResult)
def run_reconciliation(
    run_date: Optional[ddate] = Query(None, description="Defaults to today."),
    db: Session = Depends(get_db),
):
    """Section 6.4 — execute coverage / leave-integrity / preview-vs-actual."""
    if run_date is None:
        run_date = ddate.today()
    return reconciliation_service.run(db, run_date)


@router.get("/findings", response_model=List[ReconciliationFindingOut])
def list_findings(
    run_date: Optional[ddate] = None,
    check_type: Optional[ReconciliationCheckType] = None,
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(ReconciliationFinding)
    if run_date is not None:
        q = q.filter(ReconciliationFinding.run_date == run_date)
    if check_type is not None:
        q = q.filter(ReconciliationFinding.check_type == check_type)
    if agent_id is not None:
        q = q.filter(ReconciliationFinding.agent_id == agent_id)
    return q.order_by(ReconciliationFinding.created_at.desc()).all()


@router.get("/pending-approvals", response_model=List[PendingApprovalOut])
def pending_approvals(
    agent_id: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """Section 6.3 — MANAGER_APPROVAL queue."""
    q = db.query(PendingApproval)
    if agent_id is not None:
        q = q.filter(PendingApproval.agent_id == agent_id)
    if status_filter is not None:
        q = q.filter(PendingApproval.status == status_filter)
    return q.order_by(PendingApproval.created_at.desc()).all()


@router.post("/pending-approvals/{pending_id}/decision", response_model=PendingApprovalOut)
def decide_pending(
    pending_id: int, payload: ApprovalDecisionRequest, db: Session = Depends(get_db)
):
    """Section 6.3 — manager approves or denies a pending absence."""
    pending = db.query(PendingApproval).filter(PendingApproval.id == pending_id).first()
    if pending is None:
        raise HTTPException(status_code=404, detail="Pending approval not found")
    if pending.status != "PENDING":
        raise HTTPException(
            status_code=409, detail=f"Pending approval already in status {pending.status}."
        )
    pending = leave_service.decide_pending(db, pending, payload.decision, payload.manager_id)
    audit.log_event(
        db,
        event_type="MANAGER_DECISION",
        agent_id=pending.agent_id,
        target_id=str(pending.id),
        payload={
            "decision": payload.decision,
            "manager_id": payload.manager_id,
            "note": payload.note,
            "date": pending.date.isoformat(),
        },
        actor=payload.manager_id,
    )
    db.commit()
    db.refresh(pending)
    return pending
