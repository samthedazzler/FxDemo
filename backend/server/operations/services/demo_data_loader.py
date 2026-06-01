"""
Demo Data Loader
================
Reads and caches all supplementary CSV files from operations/data/.
Used by Tasks 9–12 to run live decisions against the generated demo dataset.

Files loaded:
  leave_entitlements.csv      — per-agent leave balances
  leave_requests.csv          — pending / approved / denied requests
  wfm_leave_allowance.csv     — max concurrent absences per team per date
  blackout_calendar.csv       — dates when leave is blocked
  scheduled_roster.csv        — planned shift start/end per agent per day
  skill_matrix.csv            — agent queue certifications
  shift_swap_requests.csv     — pending swap requests
  absence_notifications.csv   — sick calls and emergency absences
  overtime_consent.csv        — agents willing to take extra shifts
"""

import csv
import os
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# ── simple in-memory caches (loaded once per process) ────────────────────────
_leave_entitlements: Optional[List[dict]] = None
_leave_requests: Optional[List[dict]] = None
_wfm_allowance: Optional[List[dict]] = None
_blackout: Optional[List[dict]] = None
_roster: Optional[List[dict]] = None
_skills: Optional[List[dict]] = None
_swap_requests: Optional[List[dict]] = None
_absences: Optional[List[dict]] = None
_overtime: Optional[List[dict]] = None


def _csv(filename: str) -> List[dict]:
    path = os.path.join(_DATA_DIR, filename)
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f))


def _parse_date(s: str) -> Optional[date]:
    """Parse M/D/YYYY or YYYY-MM-DD strings into date objects."""
    if not s:
        return None
    s = s.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


# ── public loaders ─────────────────────────────────────────────────────────

def get_leave_entitlements() -> List[dict]:
    global _leave_entitlements
    if _leave_entitlements is None:
        _leave_entitlements = _csv("leave_entitlements.csv")
    return _leave_entitlements


def get_leave_requests() -> List[dict]:
    global _leave_requests
    if _leave_requests is None:
        _leave_requests = _csv("leave_requests.csv")
    return _leave_requests


def get_wfm_allowance() -> List[dict]:
    global _wfm_allowance
    if _wfm_allowance is None:
        _wfm_allowance = _csv("wfm_leave_allowance.csv")
    return _wfm_allowance


def get_blackout() -> List[dict]:
    global _blackout
    if _blackout is None:
        _blackout = _csv("blackout_calendar.csv")
    return _blackout


def get_roster() -> List[dict]:
    global _roster
    if _roster is None:
        _roster = _csv("scheduled_roster.csv")
    return _roster


def get_skills() -> List[dict]:
    global _skills
    if _skills is None:
        _skills = _csv("skill_matrix.csv")
    return _skills


def get_swap_requests() -> List[dict]:
    global _swap_requests
    if _swap_requests is None:
        _swap_requests = _csv("shift_swap_requests.csv")
    return _swap_requests


def get_absences() -> List[dict]:
    global _absences
    if _absences is None:
        _absences = _csv("absence_notifications.csv")
    return _absences


def get_overtime_consent() -> List[dict]:
    global _overtime
    if _overtime is None:
        _overtime = _csv("overtime_consent.csv")
    return _overtime


# ── helper lookups ─────────────────────────────────────────────────────────

def balance(agent_id: str, leave_type: str) -> float:
    """Return remaining leave balance for an agent + leave type (0.0 if not found)."""
    for r in get_leave_entitlements():
        if r["agent_id"] == agent_id and r["leave_type"] == leave_type:
            return float(r["remaining_days"])
    return 0.0


def team_of_agent(agent_id: str) -> Optional[str]:
    for r in get_roster():
        if r["agent_id"] == agent_id:
            return r["team"]
    return None


def approved_absent_count(team: str, check_date: date) -> int:
    """Count already-APPROVED absences for a team on a given date."""
    count = 0
    for r in get_leave_requests():
        if r["status"] != "APPROVED":
            continue
        start = _parse_date(r["start_date"])
        end = _parse_date(r["end_date"])
        if start and end and start <= check_date <= end:
            if team_of_agent(r["agent_id"]) == team:
                count += 1
    return count


def max_concurrent_absent(team: str, check_date: date) -> Optional[int]:
    """Return WFM allowance (max concurrent absences) for a team on a date."""
    for r in get_wfm_allowance():
        d = _parse_date(r["date"])
        if d == check_date and r["team"] == team:
            return int(r["max_concurrent_absent"])
    return None


def is_blackout(check_date: date, site: str = "Teleperformance-Dublin") -> Optional[str]:
    """Return blackout reason string if date is blacked out, else None."""
    for r in get_blackout():
        start = _parse_date(r["blackout_start"])
        end = _parse_date(r["blackout_end"])
        if start and end and start <= check_date <= end:
            return r["reason"]
    return None


def agent_queues(agent_id: str) -> List[str]:
    """Return list of queue_ids the agent is certified for."""
    return [
        r["queue_id"]
        for r in get_skills()
        if r["agent_id"] == agent_id and r["certified"].lower() == "true"
    ]


def roster_entry(agent_id: str, schedule_date: date) -> Optional[dict]:
    """Return scheduled roster row for agent on a date."""
    for r in get_roster():
        if r["agent_id"] == agent_id and _parse_date(r["schedule_date"]) == schedule_date:
            return r
    return None


def overtime_consented(agent_id: str) -> bool:
    for r in get_overtime_consent():
        if r["agent_id"] == agent_id:
            return r["consented"].lower() == "true"
    return False
