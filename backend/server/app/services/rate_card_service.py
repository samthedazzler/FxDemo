"""Rate Card Service (section 3.1 component + section 10 risk mitigation).

Holds contract metadata: hourly rate, OT multiplier, holiday multiplier,
min/max pay, currency. Emits a version_id; previews older than 24h are
recomputed (section 10 mitigation for stale rate cards).
"""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db import Agent, RateCardVersion
from finance_func.app.services.billing_engine import AgentRateInputs


def _version_id_for(agent: Agent) -> str:
    payload = {
        "agent_id": agent.agent_id,
        "base_hourly_rate": str(agent.base_hourly_rate),
        "overtime_multiplier": str(agent.overtime_multiplier),
        "holiday_multiplier": str(agent.holiday_multiplier),
        "night_differential": str(agent.night_differential),
        "min_monthly_pay": str(agent.min_monthly_pay),
        "max_monthly_pay": str(agent.max_monthly_pay) if agent.max_monthly_pay is not None else None,
        "currency": agent.currency,
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"rc-{digest[:12]}"


def snapshot(db: Session, agent: Agent) -> AgentRateInputs:
    """Return a fully-hydrated rate snapshot for the Billing Engine and persist
    a new RateCardVersion row if the contents changed."""
    version_id = _version_id_for(agent)
    existing = db.query(RateCardVersion).filter(RateCardVersion.version_id == version_id).first()
    if existing is None:
        existing = RateCardVersion(
            version_id=version_id,
            agent_id=agent.agent_id,
            snapshot={
                "base_hourly_rate": str(agent.base_hourly_rate),
                "overtime_multiplier": str(agent.overtime_multiplier),
                "holiday_multiplier": str(agent.holiday_multiplier),
                "night_differential": str(agent.night_differential),
                "min_monthly_pay": str(agent.min_monthly_pay),
                "max_monthly_pay": (
                    str(agent.max_monthly_pay) if agent.max_monthly_pay is not None else None
                ),
                "weekly_contracted_hours": agent.weekly_contracted_hours,
                "currency": agent.currency,
            },
            effective_from=datetime.utcnow(),
        )
        db.add(existing)
        db.flush()

    return AgentRateInputs(
        agent_id=agent.agent_id,
        base_hourly_rate=Decimal(agent.base_hourly_rate),
        overtime_multiplier=Decimal(agent.overtime_multiplier),
        holiday_multiplier=Decimal(agent.holiday_multiplier),
        night_differential=Decimal(agent.night_differential),
        min_monthly_pay=Decimal(agent.min_monthly_pay),
        max_monthly_pay=(
            Decimal(agent.max_monthly_pay) if agent.max_monthly_pay is not None else None
        ),
        weekly_contracted_hours=agent.weekly_contracted_hours,
        currency=agent.currency,
        rate_card_version=version_id,
    )


def latest_version_for(db: Session, agent_id: str) -> Optional[RateCardVersion]:
    return (
        db.query(RateCardVersion)
        .filter(RateCardVersion.agent_id == agent_id)
        .order_by(RateCardVersion.effective_from.desc())
        .first()
    )


def is_stale(version: RateCardVersion) -> bool:
    """Section 10 — previews older than rate_card_preview_ttl_hours are
    recomputed."""
    if version is None:
        return True
    return datetime.utcnow() - version.effective_from > timedelta(
        hours=settings.rate_card_preview_ttl_hours
    )
