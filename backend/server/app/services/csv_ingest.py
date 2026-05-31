"""Streaming CSV ingest pipeline for `Agent_Breakdown_140426.csv`.

WFM publishes per-status interval rows. This module reads the CSV one row
at a time (so memory stays bounded for arbitrarily large extracts),
aggregates them per (agent_id, local_date) using the section 11 Status ->
Pay Category mapping, then yields one daily rollup per agent-day. The
caller (`finance_service.process_breakdown`) takes it from there.

Input CSV columns we actually use (header names normalised — trailing
whitespace stripped):

    Agent Id              -> agent_id
    Status                -> WFM status (section 11)
    Vendor Site           -> site (for per-site holiday calendar, section 10)
    Local Interval Start  -> the local day this row belongs to
    Local Start Time      -> the actual local clock time of the activity
                             (used for the 22:00-06:00 night window)
    time_in_interval_m    -> minutes spent in this status in this interval

All other columns are ignored; they are time-zone-converted copies of the
above, kept in the CSV for downstream audit consumers (section 8).
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import IO, Iterable, Iterator, Optional, Union

from app.config import settings


_AGENT_ID = "Agent Id"
_STATUS = "Status"
_SITE = "Vendor Site"
# Source header is literally `local_interval_sta` (truncated). Fall back to
# `Local Interval End` if that column is blank for a given row.
_LOCAL_INTERVAL_START_CANDIDATES = ("local_interval_sta", "Local Interval Start", "Local Interval End")
_LOCAL_START_TIME = "Local Start Time"
_MINUTES = "time_in_interval_m"


@dataclass
class DailyAgentRollup:
    """Aggregated rollup for one (agent_id, local_date) — feeds straight
    into `wfm_aggregator.aggregate_status_map`."""

    agent_id: str
    work_date: date
    site: Optional[str] = None
    status_minutes: dict[str, Decimal] = field(default_factory=dict)
    night_minutes: Decimal = Decimal("0")
    row_count: int = 0


def _normalise_headers(reader: csv.DictReader) -> None:
    """Strip whitespace + BOM from the fieldnames. The source CSV has columns
    like ``Interval Start Time `` with a trailing space; in-memory buffers
    may also start with a UTF-8 BOM (``\\ufeff``). Fix in place so
    DictReader can address them deterministically."""
    if reader.fieldnames is None:
        return
    cleaned: list[str] = []
    for h in reader.fieldnames:
        if isinstance(h, str):
            cleaned.append(h.lstrip("﻿").strip())
        else:
            cleaned.append(h)
    reader.fieldnames = cleaned


def _parse_local_dt(raw: str) -> Optional[datetime]:
    """Parses the US M/D/YYYY h:mm:ss AM/PM format used throughout the CSV."""
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _is_night(local_dt: datetime) -> bool:
    """Section 4.1 / 5.1: night = 22:00 - 06:00 local."""
    start = settings.night_start_hour
    end = settings.night_end_hour
    h = local_dt.hour
    if start > end:  # wraps midnight (the default 22 -> 06)
        return h >= start or h < end
    return start <= h < end


def _coerce_minutes(raw: str) -> Decimal:
    if raw is None or raw == "":
        return Decimal("0")
    try:
        return Decimal(raw.strip())
    except Exception:
        return Decimal("0")


def stream_rollups(
    source: Union[IO[str], Path, str],
    only_agent_id: Optional[str] = None,
) -> Iterator[DailyAgentRollup]:
    """Stream the CSV row-by-row. Accumulate per (agent_id, local_date).

    Yields one `DailyAgentRollup` per (agent_id, work_date) after the file
    is exhausted. This shape is appropriate because the Billing Engine
    operates per agent-day — partial rollups would be replayed anyway.
    """
    rollups: dict[tuple[str, date], DailyAgentRollup] = {}

    def _iter_rows(opened: IO[str]) -> Iterator[dict]:
        reader = csv.DictReader(opened)
        _normalise_headers(reader)
        for row in reader:
            yield row

    if isinstance(source, (str, Path)):
        with open(source, "r", encoding="utf-8-sig", newline="") as fh:
            row_iter = _iter_rows(fh)
            for row in row_iter:
                _accumulate(row, rollups, only_agent_id)
    else:
        # File-like (e.g., FastAPI UploadFile.file). Make sure it's text.
        row_iter = _iter_rows(source)
        for row in row_iter:
            _accumulate(row, rollups, only_agent_id)

    # Deterministic emission order: agent_id then date.
    for key in sorted(rollups.keys()):
        yield rollups[key]


def _accumulate(
    row: dict,
    rollups: dict[tuple[str, date], DailyAgentRollup],
    only_agent_id: Optional[str],
) -> None:
    agent_id = (row.get(_AGENT_ID) or "").strip()
    if not agent_id:
        return
    if only_agent_id is not None and agent_id != only_agent_id:
        return

    status = (row.get(_STATUS) or "").strip()
    if not status:
        return

    local_interval = None
    for col in _LOCAL_INTERVAL_START_CANDIDATES:
        local_interval = _parse_local_dt(row.get(col, ""))
        if local_interval is not None:
            break
    if local_interval is None:
        return
    work_date = local_interval.date()

    minutes = _coerce_minutes(row.get(_MINUTES, ""))
    if minutes <= 0:
        return

    site = (row.get(_SITE) or "").strip() or None
    local_start = _parse_local_dt(row.get(_LOCAL_START_TIME, "")) or local_interval

    key = (agent_id, work_date)
    rollup = rollups.get(key)
    if rollup is None:
        rollup = DailyAgentRollup(agent_id=agent_id, work_date=work_date, site=site)
        rollups[key] = rollup

    if rollup.site is None and site is not None:
        rollup.site = site

    rollup.status_minutes[status] = rollup.status_minutes.get(status, Decimal("0")) + minutes
    rollup.row_count += 1

    if _is_night(local_start):
        rollup.night_minutes += minutes


def stream_rollups_from_text(text: str) -> Iterator[DailyAgentRollup]:
    """Convenience for tests."""
    return stream_rollups(StringIO(text))
