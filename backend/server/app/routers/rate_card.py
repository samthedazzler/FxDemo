"""Rate Card Service endpoints (section 3.1 component + section 10 mitigation).

Read-only views over the immutable rate-card history. Agents themselves are
mutated via /agents; each mutation that affects pricing produces a new
RateCardVersion row whose version_id is returned with every billing
record (section 8 — auditability)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Any, Dict

from app.database import get_db
from app.models.db import Agent, RateCardVersion
from app.services import rate_card_service

router = APIRouter(prefix="/rate-card", tags=["Rate Card Service"])


class RateCardVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version_id: str
    agent_id: str
    snapshot: Dict[str, Any]
    effective_from: datetime


@router.get("/{agent_id}/current", response_model=RateCardVersionOut)
def current_rate_card(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.agent_id == agent_id).first()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    # ensure snapshot exists
    rate_card_service.snapshot(db, agent)
    db.commit()
    version = rate_card_service.latest_version_for(db, agent_id)
    return version


@router.get("/{agent_id}/history", response_model=List[RateCardVersionOut])
def rate_card_history(agent_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(RateCardVersion)
        .filter(RateCardVersion.agent_id == agent_id)
        .order_by(RateCardVersion.effective_from.desc())
        .all()
    )
    return rows
