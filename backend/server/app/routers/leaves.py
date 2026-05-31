"""Leave Ledger (section 4.2) — HR-owned CRUD + adjustments
(carryover, accrual, overspend handling per section 2.1)."""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import Agent, LeaveLedger
from app.models.enums import LeaveType
from app.schemas.leave import (
    LeaveAdjustment,
    LeaveLedgerCreate,
    LeaveLedgerOut,
    LeaveLedgerUpdate,
)
from app.services import audit

router = APIRouter(prefix="/leaves", tags=["Leave Ledger (HR)"])


@router.get("", response_model=List[LeaveLedgerOut])
def list_leaves(
    agent_id: Optional[str] = None,
    leave_type: Optional[LeaveType] = None,
    db: Session = Depends(get_db),
):
    q = db.query(LeaveLedger)
    if agent_id is not None:
        q = q.filter(LeaveLedger.agent_id == agent_id)
    if leave_type is not None:
        q = q.filter(LeaveLedger.leave_type == leave_type)
    return q.all()


@router.post("", response_model=LeaveLedgerOut, status_code=status.HTTP_201_CREATED)
def create_leave(payload: LeaveLedgerCreate, db: Session = Depends(get_db)):
    if db.query(Agent).filter(Agent.agent_id == payload.agent_id).first() is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if (
        db.query(LeaveLedger)
        .filter(
            LeaveLedger.agent_id == payload.agent_id,
            LeaveLedger.leave_type == payload.leave_type,
            LeaveLedger.cycle_start == payload.cycle_start,
        )
        .first()
        is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Leave ledger entry already exists for this agent/type/cycle.",
        )
    ledger = LeaveLedger(**payload.model_dump())
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


@router.patch("/{ledger_id}", response_model=LeaveLedgerOut)
def update_leave(ledger_id: int, payload: LeaveLedgerUpdate, db: Session = Depends(get_db)):
    ledger = db.query(LeaveLedger).filter(LeaveLedger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=404, detail="Leave ledger not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(ledger, k, v)
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


@router.post("/{ledger_id}/adjust", response_model=LeaveLedgerOut)
def adjust_leave(ledger_id: int, payload: LeaveAdjustment, db: Session = Depends(get_db)):
    """Section 2.1 — carryover / accrual / overspend correction."""
    ledger = db.query(LeaveLedger).filter(LeaveLedger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=404, detail="Leave ledger not found")
    prior = Decimal(ledger.approved_balance)
    ledger.approved_balance = prior + payload.delta
    db.add(ledger)
    audit.log_event(
        db,
        event_type="LEAVE_BALANCE_ADJUSTED",
        agent_id=ledger.agent_id,
        target_id=str(ledger.id),
        payload={
            "leave_type": ledger.leave_type.value,
            "prior_approved_balance": str(prior),
            "delta": str(payload.delta),
            "new_approved_balance": str(ledger.approved_balance),
            "reason": payload.reason,
        },
        actor="hr",
    )
    db.commit()
    db.refresh(ledger)
    return ledger


@router.delete("/{ledger_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_leave(ledger_id: int, db: Session = Depends(get_db)):
    ledger = db.query(LeaveLedger).filter(LeaveLedger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=404, detail="Leave ledger not found")
    db.delete(ledger)
    db.commit()
    return None
