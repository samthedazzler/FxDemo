"""Drives the streaming CSV ingest into the existing Billing Engine.

For each daily rollup the CSV produces, this module:
    1. Looks up the Agent Master to derive `scheduled_minutes` from
       `weekly_contracted_hours` (5 working days per week).
    2. Checks the per-site holiday calendar (section 10 mitigation).
    3. Routes the {status -> minutes} map through `wfm_aggregator` (section 11).
    4. Hands the resulting `HourlyBreakdownIn` to `finance_service.process_breakdown`
       so the full deterministic chain runs unchanged.

Each yielded record carries enough detail for the Java frontend to render
a live progress feed (Server-Sent Events) over the ingest window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import IO, Iterator, Optional, Union

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.db import Agent, HolidayCalendar
from app.services import csv_ingest, wfm_aggregator
from finance_func.app.services import finance_service
from app.services.csv_ingest import DailyAgentRollup


DEFAULT_DAILY_MINUTES = Decimal("480")  # 8h * 60m


@dataclass
class IngestResult:
    agent_id: str
    work_date: date
    status: str  # OK | BLOCKED | SKIPPED_UNKNOWN_AGENT | ERROR
    daily_gross: Optional[Decimal] = None
    currency: Optional[str] = None
    billing_status: Optional[str] = None
    rate_card_version: Optional[str] = None
    content_hash: Optional[str] = None
    site: Optional[str] = None
    row_count: int = 0
    night_minutes: Decimal = Decimal("0")
    alerts: list[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "agent_id": self.agent_id,
            "work_date": self.work_date.isoformat(),
            "status": self.status,
            "daily_gross": (str(self.daily_gross) if self.daily_gross is not None else None),
            "currency": self.currency,
            "billing_status": self.billing_status,
            "rate_card_version": self.rate_card_version,
            "content_hash": self.content_hash,
            "site": self.site,
            "row_count": self.row_count,
            "night_minutes": str(self.night_minutes),
            "alerts": self.alerts or [],
            "error": self.error,
        }
        return d


def _scheduled_minutes_for(agent: Optional[Agent]) -> Decimal:
    if agent is None or not agent.weekly_contracted_hours:
        return DEFAULT_DAILY_MINUTES
    return (Decimal(agent.weekly_contracted_hours) * Decimal(60)) / Decimal(5)


def _is_holiday(db: Session, site: Optional[str], work_date: date) -> bool:
    if site is None:
        return False
    return (
        db.query(HolidayCalendar)
        .filter(HolidayCalendar.site == site, HolidayCalendar.date == work_date)
        .first()
        is not None
    )


def process_rollup(
    db: Session,
    rollup: DailyAgentRollup,
    auto_create_unknown_agents: bool = False,
) -> IngestResult:
    """Run one rollup through the full pipeline; never raises — failures are
    returned as `IngestResult.status='ERROR'` so the surrounding stream can
    keep going."""
    agent = db.query(Agent).filter(Agent.agent_id == rollup.agent_id).first()
    if agent is None and not auto_create_unknown_agents:
        return IngestResult(
            agent_id=rollup.agent_id,
            work_date=rollup.work_date,
            status="SKIPPED_UNKNOWN_AGENT",
            site=rollup.site,
            row_count=rollup.row_count,
            night_minutes=rollup.night_minutes,
            error=f"Agent {rollup.agent_id} not in Agent Master. Create via POST /agents.",
        )

    if agent is None:
        # Best-effort placeholder using safe defaults so the chain can still run.
        agent = Agent(
            agent_id=rollup.agent_id,
            contract_type="FULL_TIME",
            base_hourly_rate=Decimal("0"),
            min_monthly_pay=Decimal("0"),
            max_monthly_pay=None,
            weekly_contracted_hours=40,
            overtime_multiplier=Decimal("1.5"),
            holiday_multiplier=Decimal("2.0"),
            night_differential=Decimal("0.10"),
            currency="EUR",
            primary_site=rollup.site,
        )
        db.add(agent)
        db.flush()

    site = rollup.site or agent.primary_site
    is_holiday = _is_holiday(db, site, rollup.work_date)

    hb = wfm_aggregator.aggregate_status_map(
        agent_id=rollup.agent_id,
        work_date=rollup.work_date,
        status_minutes={k: float(v) for k, v in rollup.status_minutes.items()},
        scheduled_minutes=_scheduled_minutes_for(agent),
        is_holiday=is_holiday,
        night_minutes=rollup.night_minutes,
        site=site,
    )

    try:
        _, response = finance_service.process_breakdown(db, hb)
    except HTTPException as exc:
        return IngestResult(
            agent_id=rollup.agent_id,
            work_date=rollup.work_date,
            status="BLOCKED" if exc.status_code == 409 else "ERROR",
            site=site,
            row_count=rollup.row_count,
            night_minutes=rollup.night_minutes,
            error=str(exc.detail),
        )
    except Exception as exc:  # noqa: BLE001 — stream-must-not-die
        return IngestResult(
            agent_id=rollup.agent_id,
            work_date=rollup.work_date,
            status="ERROR",
            site=site,
            row_count=rollup.row_count,
            night_minutes=rollup.night_minutes,
            error=repr(exc),
        )

    return IngestResult(
        agent_id=rollup.agent_id,
        work_date=rollup.work_date,
        status="OK",
        daily_gross=response.daily_gross,
        currency=hb.source_status_breakdown and agent.currency,
        billing_status=response.billing_status.value,
        rate_card_version=response.rate_card_version,
        content_hash=response.content_hash,
        site=site,
        row_count=rollup.row_count,
        night_minutes=rollup.night_minutes,
        alerts=response.alerts,
    )


def stream_ingest(
    db: Session,
    source: Union[IO[str], Path, str],
    only_agent_id: Optional[str] = None,
    auto_create_unknown_agents: bool = False,
) -> Iterator[IngestResult]:
    """Streaming generator: parses CSV row-by-row, aggregates per agent-day,
    pushes each rollup through the Billing Engine, yields one `IngestResult`
    per agent-day."""
    for rollup in csv_ingest.stream_rollups(source, only_agent_id=only_agent_id):
        yield process_rollup(db, rollup, auto_create_unknown_agents)
