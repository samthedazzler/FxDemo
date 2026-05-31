"""Section 10 — Holiday calendar is per-site, not global. Multi-site agents
resolve by primary site."""

from datetime import date as ddate
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import HolidayCalendar

router = APIRouter(prefix="/holidays", tags=["Holiday Calendar"])


class HolidayIn(BaseModel):
    site: str
    date: ddate
    name: Optional[str] = None


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    site: str
    date: ddate
    name: Optional[str] = None


@router.get("", response_model=List[HolidayOut])
def list_holidays(site: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(HolidayCalendar)
    if site is not None:
        q = q.filter(HolidayCalendar.site == site)
    return q.order_by(HolidayCalendar.date.asc()).all()


@router.post("", response_model=HolidayOut, status_code=201)
def create_holiday(payload: HolidayIn, db: Session = Depends(get_db)):
    if (
        db.query(HolidayCalendar)
        .filter(HolidayCalendar.site == payload.site, HolidayCalendar.date == payload.date)
        .first()
        is not None
    ):
        raise HTTPException(status_code=409, detail="Holiday already defined for that site/date.")
    h = HolidayCalendar(**payload.model_dump())
    db.add(h)
    db.commit()
    db.refresh(h)
    return h


@router.delete("/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: int, db: Session = Depends(get_db)):
    h = db.query(HolidayCalendar).filter(HolidayCalendar.id == holiday_id).first()
    if h is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(h)
    db.commit()
    return None
