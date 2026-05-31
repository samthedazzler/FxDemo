"""
Operations CSV Loader Service
==============================
Reads Agent_Breakdown_140426.csv and provides aggregated views used by all
Operations task APIs.

CSV columns used:
  Agent Id            — unique agent identifier
  Status              — activity status (chat, after_contact_work, available,
                        break, lunch, facebook_training_meeting, ...)
  Status Group        — OCC (productive) | CFT (available/idle) | NaN (shrinkage)
  time_in_interval_m  — minutes spent in this status inside the 30-min interval
  local_interval_sta  — local interval start timestamp (30-min bucket)
  Local Interval End  — local interval end timestamp
  Local Start Time    — actual start of this activity (wall-clock)
  Local End Time      — actual end of this activity (wall-clock)
  SRT Team            — team / queue name
  Vendor Site         — site name

Status classification (aligned to BEST WFM §2.2 + Section 11 of this project):
  OCC  → chat, after_contact_work, email, email_backlog   (Transaction time)
  CFT  → available                                         (Available/idle time)
  SHRINKAGE → break, lunch                                 (In-Office Shrinkage)
  TRAINING  → facebook_training_meeting                    (In-Office Shrinkage/Training)

We trust the Status Group column from the CSV for OCC/CFT classification and
classify NaN-group rows by status name for break vs training distinction.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Path resolution ───────────────────────────────────────────────────────────
_HERE = Path(__file__).parent.parent          # operations/
DEFAULT_CSV_PATH = _HERE / "Agent_Breakdown_140426.csv"

# ── Status group constants ────────────────────────────────────────────────────
OCC_GROUP = "OCC"
CFT_GROUP = "CFT"

# Statuses that are shrinkage when Status Group is NaN / not OCC/CFT
BREAK_STATUSES = {"break", "lunch"}
TRAINING_STATUSES = {"facebook_training_meeting", "meeting", "coaching",
                     "production_training", "administrative_task"}


# ── Raw row dataclass ─────────────────────────────────────────────────────────
@dataclass
class RawRow:
    agent_id: str
    status: str
    status_group: str            # "OCC", "CFT", or empty/NaN
    time_in_interval_m: float    # minutes in this interval
    interval_start: datetime     # local 30-min bucket start
    interval_end: Optional[datetime]
    local_start: Optional[datetime]   # actual activity start
    local_end: Optional[datetime]     # actual activity end
    team: str
    site: str

    @property
    def work_date(self) -> date:
        return self.interval_start.date()


# ── Per-agent per-day aggregate ───────────────────────────────────────────────
@dataclass
class AgentDayAggregate:
    agent_id: str
    work_date: date
    team: str
    site: str

    # Minute buckets (BEST WFM §2.2 hourly breakdown model)
    occ_minutes: float = 0.0      # Transaction time (OCC group)
    cft_minutes: float = 0.0      # Available/idle time (CFT group)
    break_minutes: float = 0.0    # break + lunch  (In-Office Shrinkage)
    training_minutes: float = 0.0 # meetings / training (In-Office Shrinkage)

    first_login: Optional[datetime] = None   # earliest Local Start Time
    last_logout: Optional[datetime] = None   # latest   Local End Time

    row_count: int = 0

    # ── Derived metrics ───────────────────────────────────────────────────────

    @property
    def production_minutes(self) -> float:
        """Transaction + Available = Production Hours (BEST WFM §2.2)."""
        return self.occ_minutes + self.cft_minutes

    @property
    def in_office_shrinkage_minutes(self) -> float:
        """Break + Lunch + Training (In-Office Shrinkage per BEST WFM §2.2.4)."""
        return self.break_minutes + self.training_minutes

    @property
    def present_minutes(self) -> float:
        """Production + In-Office Shrinkage = Present Hours excl. NHT."""
        return self.production_minutes + self.in_office_shrinkage_minutes

    @property
    def total_logged_minutes(self) -> float:
        return self.present_minutes

    @property
    def productive_hours(self) -> float:
        return self.occ_minutes / 60.0

    @property
    def available_hours(self) -> float:
        return self.cft_minutes / 60.0

    @property
    def present_hours(self) -> float:
        return self.present_minutes / 60.0

    @property
    def shift_span_hours(self) -> Optional[float]:
        if self.first_login and self.last_logout:
            delta = self.last_logout - self.first_login
            return delta.total_seconds() / 3600.0
        return None

    # ── BEST WFM §1.4 Key Rates ───────────────────────────────────────────────

    @property
    def occupancy_pct(self) -> Optional[float]:
        """Occupancy = Transaction Hours / Production Hours × 100 (BEST WFM §1.4)."""
        if self.production_minutes > 0:
            return round(self.occ_minutes / self.production_minutes * 100, 2)
        return None

    @property
    def availability_rate_pct(self) -> Optional[float]:
        """Availability Rate = Available Hours / Production Hours × 100."""
        if self.production_minutes > 0:
            return round(self.cft_minutes / self.production_minutes * 100, 2)
        return None

    @property
    def in_office_shrinkage_rate_pct(self) -> Optional[float]:
        """In-Office Shrinkage Rate = Shrinkage / Present Hours × 100 (BEST WFM §1.4).
        NOTE: The simple Break+Lunch/Total formula discussed in meetings was
        flagged as incorrect. BEST WFM definition divides by Present Hours,
        not total logged minutes. Reference: ops_task_1.pdf task 2 annotation."""
        if self.present_minutes > 0:
            return round(
                self.in_office_shrinkage_minutes / self.present_minutes * 100, 2
            )
        return None

    @property
    def productivity_pct(self) -> Optional[float]:
        """Productivity % = Productive Hours / Paid Hours × 100 (ops_task_2.pdf §3).
        Paid Hours = total logged (present) hours."""
        if self.present_minutes > 0:
            return round(self.occ_minutes / self.present_minutes * 100, 2)
        return None

    @property
    def utilisation_pct(self) -> Optional[float]:
        """Utilisation = Production Hours / Present Hours × 100 (BEST WFM §1.4)."""
        if self.present_minutes > 0:
            return round(self.production_minutes / self.present_minutes * 100, 2)
        return None


# ── Per-interval (30-min) aggregate ──────────────────────────────────────────
@dataclass
class IntervalAggregate:
    work_date: date
    interval_start: datetime
    active_agents: int = 0       # agents with any OCC or CFT record
    occ_agents: int = 0          # agents in OCC (productive)
    cft_agents: int = 0          # agents in CFT (available)
    occ_minutes: float = 0.0
    cft_minutes: float = 0.0


# ── CSV parsing helpers ───────────────────────────────────────────────────────
def _parse_dt(val: str) -> Optional[datetime]:
    val = val.strip()
    if not val:
        return None
    for fmt in (
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
    ):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def _classify_row(row: RawRow) -> Tuple[str, str]:
    """Return (bucket, sub_type) where bucket is 'occ'|'cft'|'break'|'training'."""
    sg = row.status_group.strip().upper()
    if sg == OCC_GROUP:
        return "occ", row.status
    if sg == CFT_GROUP:
        return "cft", row.status
    # NaN / empty → classify by status name
    st = row.status.lower().strip()
    if st in BREAK_STATUSES:
        return "break", st
    if st in TRAINING_STATUSES:
        return "training", st
    # Default unknown to break/shrinkage to be conservative
    return "break", st


# ── Main loader ───────────────────────────────────────────────────────────────
def load_raw_rows(csv_path: Path = DEFAULT_CSV_PATH) -> List[RawRow]:
    """Parse the CSV and return every row as a RawRow."""
    rows: List[RawRow] = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for rec in reader:
            agent_id = rec.get("Agent Id", "").strip()
            if not agent_id:
                continue
            status = rec.get("Status", "").strip().lower()
            status_group = rec.get("Status Group", "").strip()
            try:
                time_m = float(rec.get("time_in_interval_m", 0) or 0)
            except (ValueError, TypeError):
                time_m = 0.0

            interval_start = _parse_dt(rec.get("local_interval_sta", ""))
            if interval_start is None:
                continue  # skip rows with no parseable interval

            rows.append(
                RawRow(
                    agent_id=agent_id,
                    status=status,
                    status_group=status_group,
                    time_in_interval_m=time_m,
                    interval_start=interval_start,
                    interval_end=_parse_dt(rec.get("Local Interval End", "")),
                    local_start=_parse_dt(rec.get("Local Start Time", "")),
                    local_end=_parse_dt(rec.get("Local End Time", "")),
                    team=rec.get("SRT Team", "").strip(),
                    site=rec.get("Vendor Site", "").strip(),
                )
            )
    return rows


def build_agent_day_aggregates(
    rows: List[RawRow],
    filter_date: Optional[date] = None,
    filter_agent: Optional[str] = None,
) -> Dict[Tuple[str, date], AgentDayAggregate]:
    """Aggregate raw rows into per-(agent, date) summaries."""
    agg: Dict[Tuple[str, date], AgentDayAggregate] = {}

    for row in rows:
        if filter_date and row.work_date != filter_date:
            continue
        if filter_agent and row.agent_id != filter_agent:
            continue

        key = (row.agent_id, row.work_date)
        if key not in agg:
            agg[key] = AgentDayAggregate(
                agent_id=row.agent_id,
                work_date=row.work_date,
                team=row.team,
                site=row.site,
            )
        rec = agg[key]
        rec.row_count += 1

        bucket, _ = _classify_row(row)
        m = row.time_in_interval_m
        if bucket == "occ":
            rec.occ_minutes += m
        elif bucket == "cft":
            rec.cft_minutes += m
        elif bucket == "break":
            rec.break_minutes += m
        elif bucket == "training":
            rec.training_minutes += m

        # Track actual shift boundaries
        if row.local_start:
            if rec.first_login is None or row.local_start < rec.first_login:
                rec.first_login = row.local_start
        if row.local_end:
            if rec.last_logout is None or row.local_end > rec.last_logout:
                rec.last_logout = row.local_end

    return agg


def build_interval_aggregates(
    rows: List[RawRow],
    filter_date: Optional[date] = None,
) -> Dict[Tuple[date, datetime], IntervalAggregate]:
    """Aggregate rows into per-(date, interval_start) summaries with agent counts."""
    # First collect agents per interval
    interval_agents: Dict[Tuple[date, datetime], Dict[str, set]] = defaultdict(
        lambda: {"occ": set(), "cft": set(), "all": set()}
    )
    interval_minutes: Dict[Tuple[date, datetime], Dict[str, float]] = defaultdict(
        lambda: {"occ": 0.0, "cft": 0.0}
    )

    for row in rows:
        if filter_date and row.work_date != filter_date:
            continue
        key = (row.work_date, row.interval_start)
        bucket, _ = _classify_row(row)
        if bucket in ("occ", "cft"):
            interval_agents[key]["all"].add(row.agent_id)
            interval_agents[key][bucket].add(row.agent_id)
            interval_minutes[key][bucket] += row.time_in_interval_m

    result: Dict[Tuple[date, datetime], IntervalAggregate] = {}
    for key, agent_sets in interval_agents.items():
        d, iv_start = key
        result[key] = IntervalAggregate(
            work_date=d,
            interval_start=iv_start,
            active_agents=len(agent_sets["all"]),
            occ_agents=len(agent_sets["occ"]),
            cft_agents=len(agent_sets["cft"]),
            occ_minutes=interval_minutes[key]["occ"],
            cft_minutes=interval_minutes[key]["cft"],
        )
    return result


def available_dates(csv_path: Path = DEFAULT_CSV_PATH) -> List[date]:
    """Return sorted list of unique work dates in the CSV."""
    rows = load_raw_rows(csv_path)
    return sorted({r.work_date for r in rows})


def available_agents(csv_path: Path = DEFAULT_CSV_PATH) -> List[str]:
    """Return sorted list of unique agent IDs in the CSV."""
    rows = load_raw_rows(csv_path)
    return sorted({r.agent_id for r in rows})


# ── Singleton cache (loaded once per process) ─────────────────────────────────
_ROW_CACHE: Optional[List[RawRow]] = None


def get_rows(csv_path: Path = DEFAULT_CSV_PATH) -> List[RawRow]:
    """Return cached rows; reload if csv_path differs from cached source."""
    global _ROW_CACHE
    if _ROW_CACHE is None:
        _ROW_CACHE = load_raw_rows(csv_path)
    return _ROW_CACHE


def invalidate_cache() -> None:
    global _ROW_CACHE
    _ROW_CACHE = None
