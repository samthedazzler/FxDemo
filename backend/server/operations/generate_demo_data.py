"""
Generates all supplementary CSV datasets for Operations Tasks 9–12 demo.
Run from repo root:  python operations/generate_demo_data.py
Output folder:  operations/data/
"""

import csv
import os
import random
import uuid
from datetime import date, datetime

random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Master constants — must mirror actual CSV
# ─────────────────────────────────────────────────────────────────────────────

TEAM_GE = "Account Access - Genpop HTS - General Entrypoints - TP - Dublin"
TEAM_ID = "Account Access - Genpop HTS - Incorrect Disables - TP - Dublin"
SITE    = "Teleperformance-Dublin"
ORG     = "Teleperformance"

GE_AGENTS = [
    "61581635771227", "61581666459416", "61581674139184",
    "61582253126069", "61583018368573", "61585038341143",
    "61587856425159", "61588190284154", "61588377774860",
    "61588388064451", "61588389996727",
]
ID_AGENTS = [
    "100071773725249", "61580771977862", "61580818484348",
    "61581055615480",  "61581509267603", "61581904917164",
    "61581980363535",  "61588063300667", "61588449381350",
]
ALL_AGENTS = GE_AGENTS + ID_AGENTS

def team_of(aid):
    return TEAM_GE if aid in GE_AGENTS else TEAM_ID


# ─────────────────────────────────────────────────────────────────────────────
# 1. LEAVE ENTITLEMENTS
# ─────────────────────────────────────────────────────────────────────────────

entitlements = []
for aid in ALL_AGENTS:
    annual_used = random.randint(2, 7)
    entitlements.append({
        "agent_id": aid, "leave_type": "ANNUAL",
        "entitlement_days": 20, "used_days": annual_used,
        "remaining_days": 20 - annual_used, "year": 2026,
    })
    sick_used = random.choice([0, 0, 0, 1, 1, 2])
    entitlements.append({
        "agent_id": aid, "leave_type": "SICK",
        "entitlement_days": 5, "used_days": sick_used,
        "remaining_days": 5 - sick_used, "year": 2026,
    })
    personal_used = random.choice([0, 0, 1])
    entitlements.append({
        "agent_id": aid, "leave_type": "PERSONAL",
        "entitlement_days": 2, "used_days": personal_used,
        "remaining_days": 2 - personal_used, "year": 2026,
    })

# Edge case: 61580771977862 exhausted annual leave → DENY: INSUFFICIENT_BALANCE demo
for r in entitlements:
    if r["agent_id"] == "61580771977862" and r["leave_type"] == "ANNUAL":
        r["used_days"] = 20
        r["remaining_days"] = 0

_path = os.path.join(DATA_DIR, "leave_entitlements.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["agent_id", "leave_type", "entitlement_days",
                                       "used_days", "remaining_days", "year"])
    w.writeheader()
    w.writerows(entitlements)
print(f"  leave_entitlements.csv        {len(entitlements):>4} rows")


# ─────────────────────────────────────────────────────────────────────────────
# 2. LEAVE REQUESTS
# ─────────────────────────────────────────────────────────────────────────────

def uid(n):
    return str(uuid.UUID(int=n))


leave_requests = [
    # ── PENDING → will GRANT (balance OK, team has room, no blackout) ─────────
    {
        "request_id": uid(1),       "agent_id": "61581666459416",
        "leave_type": "ANNUAL",     "start_date": "4/15/2026",   "end_date": "4/15/2026",
        "days_requested": 1,        "status": "PENDING",
        "submitted_at": "4/12/2026 9:14:00 AM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
    # ── PENDING → will GRANT (2-day break, team has room) ──────────────────
    {
        "request_id": uid(2),       "agent_id": "61582253126069",
        "leave_type": "ANNUAL",     "start_date": "4/16/2026",   "end_date": "4/17/2026",
        "days_requested": 2,        "status": "PENDING",
        "submitted_at": "4/13/2026 8:45:00 AM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
    # ── PENDING → DENY: INSUFFICIENT_BALANCE (0 annual days left) ──────────
    {
        "request_id": uid(3),       "agent_id": "61580771977862",
        "leave_type": "ANNUAL",     "start_date": "4/20/2026",   "end_date": "4/20/2026",
        "days_requested": 1,        "status": "PENDING",
        "submitted_at": "4/14/2026 10:02:00 AM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
    # ── PENDING → DENY: TEAM_AT_CAPACITY (61581635771227 already approved Apr 22) ──
    {
        "request_id": uid(4),       "agent_id": "61581674139184",
        "leave_type": "ANNUAL",     "start_date": "4/22/2026",   "end_date": "4/22/2026",
        "days_requested": 1,        "status": "PENDING",
        "submitted_at": "4/14/2026 11:30:00 AM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
    # ── PENDING → DENY: BLACKOUT_DATE (peak season Apr 25 – May 5) ─────────
    {
        "request_id": uid(5),       "agent_id": "61583018368573",
        "leave_type": "ANNUAL",     "start_date": "4/28/2026",   "end_date": "4/29/2026",
        "days_requested": 2,        "status": "PENDING",
        "submitted_at": "4/12/2026 2:10:00 PM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
    # ── APPROVED (pre-decided, holds the Apr 22 GE team slot) ──────────────
    {
        "request_id": uid(6),       "agent_id": "61581635771227",
        "leave_type": "ANNUAL",     "start_date": "4/22/2026",   "end_date": "4/22/2026",
        "days_requested": 1,        "status": "APPROVED",
        "submitted_at": "4/7/2026 9:00:00 AM",
        "decided_at": "4/8/2026 10:15:00 AM",
        "decided_by": "ops_supervisor_01",  "deny_reason": "",
    },
    # ── APPROVED sick leave (agent absent Apr 13, already processed) ─────
    {
        "request_id": uid(7),       "agent_id": "61581509267603",
        "leave_type": "SICK",       "start_date": "4/13/2026",   "end_date": "4/13/2026",
        "days_requested": 1,        "status": "APPROVED",
        "submitted_at": "4/13/2026 7:58:00 AM",
        "decided_at": "4/13/2026 8:05:00 AM",
        "decided_by": "ops_supervisor_01",  "deny_reason": "",
    },
    # ── DENIED (historic — blackout date, same agent tried earlier) ───────
    {
        "request_id": uid(8),       "agent_id": "61585038341143",
        "leave_type": "ANNUAL",     "start_date": "4/28/2026",   "end_date": "4/28/2026",
        "days_requested": 1,        "status": "DENIED",
        "submitted_at": "4/10/2026 3:00:00 PM",
        "decided_at": "4/11/2026 9:00:00 AM",
        "decided_by": "ops_supervisor_01",
        "deny_reason": "BLACKOUT_DATE: peak season Apr 25 - May 5",
    },
    # ── PENDING → will GRANT (personal day, ID team) ─────────────────────
    {
        "request_id": uid(9),       "agent_id": "61587856425159",
        "leave_type": "PERSONAL",   "start_date": "4/18/2026",   "end_date": "4/18/2026",
        "days_requested": 1,        "status": "PENDING",
        "submitted_at": "4/14/2026 4:45:00 PM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
    # ── PENDING → will GRANT (ID team, Apr 17) ───────────────────────────
    {
        "request_id": uid(10),      "agent_id": "61588063300667",
        "leave_type": "ANNUAL",     "start_date": "4/17/2026",   "end_date": "4/17/2026",
        "days_requested": 1,        "status": "PENDING",
        "submitted_at": "4/13/2026 1:30:00 PM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
    # ── PENDING → will GRANT (sick, balance available) ─────────────────
    {
        "request_id": uid(11),      "agent_id": "61581904917164",
        "leave_type": "SICK",       "start_date": "4/14/2026",   "end_date": "4/14/2026",
        "days_requested": 1,        "status": "PENDING",
        "submitted_at": "4/14/2026 7:52:00 AM",
        "decided_at": "",           "decided_by": "",             "deny_reason": "",
    },
]

_path = os.path.join(DATA_DIR, "leave_requests.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "request_id", "agent_id", "leave_type", "start_date", "end_date",
        "days_requested", "status", "submitted_at", "decided_at", "decided_by", "deny_reason",
    ])
    w.writeheader()
    w.writerows(leave_requests)
print(f"  leave_requests.csv            {len(leave_requests):>4} rows")


# ─────────────────────────────────────────────────────────────────────────────
# 3. WFM LEAVE ALLOWANCE
# ─────────────────────────────────────────────────────────────────────────────

allowance_dates = [
    date(2026, 4, 12), date(2026, 4, 13), date(2026, 4, 14),
    date(2026, 4, 15), date(2026, 4, 16), date(2026, 4, 17), date(2026, 4, 18),
    date(2026, 4, 20), date(2026, 4, 21), date(2026, 4, 22),
]
allowance_rows = []
for d in allowance_dates:
    ds = f"{d.month}/{d.day}/{d.year}"
    allowance_rows.append({
        "team": TEAM_GE, "date": ds, "team_size": len(GE_AGENTS),
        "max_concurrent_absent": 1,
        "max_absence_pct": round(1 / len(GE_AGENTS) * 100, 1),
    })
    allowance_rows.append({
        "team": TEAM_ID, "date": ds, "team_size": len(ID_AGENTS),
        "max_concurrent_absent": 1,
        "max_absence_pct": round(1 / len(ID_AGENTS) * 100, 1),
    })

_path = os.path.join(DATA_DIR, "wfm_leave_allowance.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["team", "date", "team_size",
                                       "max_concurrent_absent", "max_absence_pct"])
    w.writeheader()
    w.writerows(allowance_rows)
print(f"  wfm_leave_allowance.csv       {len(allowance_rows):>4} rows")


# ─────────────────────────────────────────────────────────────────────────────
# 4. BLACKOUT CALENDAR
# ─────────────────────────────────────────────────────────────────────────────

blackout_rows = [
    {
        "site": SITE, "blackout_start": "4/25/2026", "blackout_end": "5/5/2026",
        "reason": "PEAK_SEASON",
        "notes": "End-of-month billing cycle plus public holiday coverage — no leave permitted",
    },
    {
        "site": SITE, "blackout_start": "5/4/2026", "blackout_end": "5/4/2026",
        "reason": "PUBLIC_HOLIDAY",
        "notes": "May Bank Holiday — mandatory staffing day, all-hands",
    },
    {
        "site": SITE, "blackout_start": "6/6/2026", "blackout_end": "6/7/2026",
        "reason": "MANDATORY_COVERAGE",
        "notes": "CRM platform migration weekend — all agents required on-site",
    },
]

_path = os.path.join(DATA_DIR, "blackout_calendar.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["site", "blackout_start", "blackout_end", "reason", "notes"])
    w.writeheader()
    w.writerows(blackout_rows)
print(f"  blackout_calendar.csv         {len(blackout_rows):>4} rows")


# ─────────────────────────────────────────────────────────────────────────────
# 5. SCHEDULED ROSTER
# ─────────────────────────────────────────────────────────────────────────────
# Three shift patterns for Teleperformance-Dublin contact centre:
#   MORNING:  08:00–16:30  break 12:00–12:30  queue: EMAIL + CHAT
#   DAY:      09:00–17:30  break 13:00–13:30  queue: EMAIL + EMAIL_BACKLOG
#   WEEKEND:  10:00–16:00  break 12:30–13:00  queue: EMAIL (reduced coverage)
# Apr 12 = Sunday → WEEKEND shift for everyone
# Apr 13 = Monday → MORNING or DAY (alternate by agent index)
# Apr 14 = Tuesday → same as Monday (stable roster)

SHIFT_PATTERNS = {
    "MORNING": {
        "scheduled_start": "08:00",
        "scheduled_end":   "16:30",
        "break_start":     "12:00",
        "break_end":       "12:30",
        "shift_hours":     8.5,
    },
    "DAY": {
        "scheduled_start": "09:00",
        "scheduled_end":   "17:30",
        "break_start":     "13:00",
        "break_end":       "13:30",
        "shift_hours":     8.5,
    },
    "WEEKEND": {
        "scheduled_start": "10:00",
        "scheduled_end":   "16:00",
        "break_start":     "12:30",
        "break_end":       "13:00",
        "shift_hours":     6.0,
    },
}

QUEUE_BY_SHIFT = {
    "MORNING": "QUEUE_EMAIL",
    "DAY":     "QUEUE_EMAIL_BACKLOG",
    "WEEKEND": "QUEUE_EMAIL",
}

# agent 61581509267603 is SICK on Apr 13 — mark as ABSENT in roster
ABSENT_MAP = {("61581509267603", "4/13/2026")}

roster_rows = []
csv_dates = [
    (date(2026, 4, 12), "4/12/2026", "WEEKEND"),
    (date(2026, 4, 13), "4/13/2026", None),  # alternating MORNING/DAY
    (date(2026, 4, 14), "4/14/2026", None),
]

for i, aid in enumerate(ALL_AGENTS):
    for d_obj, d_str, override_shift in csv_dates:
        if override_shift:
            shift_type = override_shift
        else:
            shift_type = "MORNING" if i % 2 == 0 else "DAY"

        sp = SHIFT_PATTERNS[shift_type]
        queue = QUEUE_BY_SHIFT[shift_type]

        # 61581674139184 works CHAT queue on weekdays
        if aid == "61581674139184" and shift_type != "WEEKEND":
            queue = "QUEUE_CHAT"

        absent = (aid, d_str) in ABSENT_MAP
        status = "ABSENT_SICK" if absent else "SCHEDULED"

        roster_rows.append({
            "agent_id":            aid,
            "team":                team_of(aid),
            "site":                SITE,
            "schedule_date":       d_str,
            "shift_type":          shift_type,
            "scheduled_start":     f"{d_str} {sp['scheduled_start']}",
            "scheduled_end":       f"{d_str} {sp['scheduled_end']}",
            "scheduled_break_start": f"{d_str} {sp['break_start']}",
            "scheduled_break_end": f"{d_str} {sp['break_end']}",
            "scheduled_hours":     sp["shift_hours"],
            "queue_assignment":    queue,
            "roster_status":       status,
        })

_path = os.path.join(DATA_DIR, "scheduled_roster.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "agent_id", "team", "site", "schedule_date", "shift_type",
        "scheduled_start", "scheduled_end",
        "scheduled_break_start", "scheduled_break_end",
        "scheduled_hours", "queue_assignment", "roster_status",
    ])
    w.writeheader()
    w.writerows(roster_rows)
print(f"  scheduled_roster.csv          {len(roster_rows):>4} rows  ({len(ALL_AGENTS)} agents × 3 days)")


# ─────────────────────────────────────────────────────────────────────────────
# 6. SKILL MATRIX
# ─────────────────────────────────────────────────────────────────────────────
# Queues used in this contact centre
QUEUES = {
    "QUEUE_EMAIL":         "Email — standard inbound",
    "QUEUE_EMAIL_BACKLOG": "Email — backlog clearing",
    "QUEUE_CHAT":          "Live chat",
    "QUEUE_SOCIAL_MEDIA":  "Social media / Facebook",
    "QUEUE_ACW":           "After-contact work (post-call)",
}

# Every agent is certified for EMAIL + ACW
# Experienced agents (first half of each team list) also handle 2 more queues
# Edge: agent 61580818484348 NOT certified for EMAIL_BACKLOG (used in replacement demo)
skill_rows = []
for i, aid in enumerate(ALL_AGENTS):
    is_experienced = (i % 3 != 0)   # 2/3 are experienced

    certifications = {
        "QUEUE_EMAIL":   (True, 4),
        "QUEUE_ACW":     (True, 5),
    }
    if is_experienced:
        certifications["QUEUE_EMAIL_BACKLOG"] = (True, 3)
    if i % 4 == 0:
        certifications["QUEUE_CHAT"] = (True, 3)
    if i % 5 == 0:
        certifications["QUEUE_SOCIAL_MEDIA"] = (True, 2)

    # Override: 61580818484348 — NOT certified for EMAIL_BACKLOG (demo: skill mismatch)
    if aid == "61580818484348":
        certifications.pop("QUEUE_EMAIL_BACKLOG", None)
        certifications["QUEUE_EMAIL_BACKLOG"] = (False, 0)

    # 61581674139184 is the CHAT specialist
    if aid == "61581674139184":
        certifications["QUEUE_CHAT"] = (True, 5)

    for qid, (certified, proficiency) in certifications.items():
        skill_rows.append({
            "agent_id":        aid,
            "team":            team_of(aid),
            "queue_id":        qid,
            "queue_name":      QUEUES[qid],
            "certified":       certified,
            "proficiency":     proficiency,
            "certified_since": f"1/{random.randint(1, 12)}/202{random.randint(3, 5)}",
        })

_path = os.path.join(DATA_DIR, "skill_matrix.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "agent_id", "team", "queue_id", "queue_name",
        "certified", "proficiency", "certified_since",
    ])
    w.writeheader()
    w.writerows(skill_rows)
print(f"  skill_matrix.csv              {len(skill_rows):>4} rows")


# ─────────────────────────────────────────────────────────────────────────────
# 7. SHIFT SWAP REQUESTS
# ─────────────────────────────────────────────────────────────────────────────
swap_requests = [
    # ── PENDING → APPROVE: skill match, hours OK, coverage floor held ───────
    # Agent 61581635771227 (MORNING Apr 14) swaps with 61581666459416 (MORNING Apr 13)
    {
        "request_id":   uid(101),
        "agent_a_id":   "61581635771227",   "agent_a_date": "4/14/2026",
        "agent_b_id":   "61581666459416",   "agent_b_date": "4/13/2026",
        "reason":       "Personal appointment on Apr 14 morning",
        "status":       "PENDING",
        "submitted_at": "4/12/2026 5:30:00 PM",
        "decided_at":   "",   "decided_by": "",   "deny_reason": "",
    },
    # ── PENDING → APPROVE: ID team internal swap ─────────────────────────
    {
        "request_id":   uid(102),
        "agent_a_id":   "61580818484348",   "agent_a_date": "4/14/2026",
        "agent_b_id":   "61581055615480",   "agent_b_date": "4/13/2026",
        "reason":       "Family commitment",
        "status":       "PENDING",
        "submitted_at": "4/13/2026 9:00:00 AM",
        "decided_at":   "",   "decided_by": "",   "deny_reason": "",
    },
    # ── PENDING → DENY: SKILL_MISMATCH
    # 61580771977862 (QUEUE_EMAIL_BACKLOG) wants to swap with 61581674139184 (QUEUE_CHAT)
    # 61580771977862 is NOT certified for QUEUE_CHAT
    {
        "request_id":   uid(103),
        "agent_a_id":   "61580771977862",   "agent_a_date": "4/13/2026",
        "agent_b_id":   "61581674139184",   "agent_b_date": "4/14/2026",
        "reason":       "Prefer afternoon shift",
        "status":       "PENDING",
        "submitted_at": "4/13/2026 11:15:00 AM",
        "decided_at":   "",   "decided_by": "",   "deny_reason": "",
    },
    # ── APPROVED (historic) ──────────────────────────────────────────────
    {
        "request_id":   uid(104),
        "agent_a_id":   "61583018368573",   "agent_a_date": "4/13/2026",
        "agent_b_id":   "61585038341143",   "agent_b_date": "4/14/2026",
        "reason":       "Doctor appointment",
        "status":       "APPROVED",
        "submitted_at": "4/10/2026 3:45:00 PM",
        "decided_at":   "4/11/2026 8:30:00 AM",
        "decided_by":   "ops_supervisor_01",   "deny_reason": "",
    },
    # ── DENIED (historic — coverage floor breach) ────────────────────────
    {
        "request_id":   uid(105),
        "agent_a_id":   "61588377774860",   "agent_a_date": "4/12/2026",
        "agent_b_id":   "61588388064451",   "agent_b_date": "4/14/2026",
        "reason":       "Weekend preference swap",
        "status":       "DENIED",
        "submitted_at": "4/9/2026 4:00:00 PM",
        "decided_at":   "4/10/2026 9:15:00 AM",
        "decided_by":   "ops_supervisor_01",
        "deny_reason":  "COVERAGE_FLOOR_BREACH: Apr 12 (Sunday) already at minimum staffing",
    },
]

_path = os.path.join(DATA_DIR, "shift_swap_requests.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "request_id", "agent_a_id", "agent_a_date", "agent_b_id", "agent_b_date",
        "reason", "status", "submitted_at", "decided_at", "decided_by", "deny_reason",
    ])
    w.writeheader()
    w.writerows(swap_requests)
print(f"  shift_swap_requests.csv       {len(swap_requests):>4} rows")


# ─────────────────────────────────────────────────────────────────────────────
# 8. ABSENCE NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────
absence_rows = [
    # Sick call — agent absent Apr 13 (matches APPROVED sick leave request uid(7))
    {
        "notification_id": uid(201),
        "agent_id":        "61581509267603",
        "absence_date":    "4/13/2026",
        "absence_type":    "SICK",
        "notified_at":     "4/13/2026 7:55:00 AM",
        "notified_by":     "agent_self_report",
        "notes":           "Agent called in sick via HR portal. GP cert to follow.",
        "replacement_assigned": "",
    },
    # Emergency absence — agent unable to come in Apr 14
    {
        "notification_id": uid(202),
        "agent_id":        "61581904917164",
        "absence_date":    "4/14/2026",
        "absence_type":    "EMERGENCY",
        "notified_at":     "4/14/2026 7:48:00 AM",
        "notified_by":     "team_lead",
        "notes":           "Family emergency. Agent notified team lead by phone.",
        "replacement_assigned": "",
    },
    # Late arrival flagged as partial absence — agent 61580771977862 came in 45 min late Apr 12
    {
        "notification_id": uid(203),
        "agent_id":        "61580771977862",
        "absence_date":    "4/12/2026",
        "absence_type":    "LATE_ARRIVAL",
        "notified_at":     "4/12/2026 10:47:00 AM",
        "notified_by":     "system_auto_flag",
        "notes":           "First login 45 min after scheduled start. Transport delay reported.",
        "replacement_assigned": "",
    },
    # Historic absence — already covered (for replacement demo context)
    {
        "notification_id": uid(204),
        "agent_id":        "61582253126069",
        "absence_date":    "4/10/2026",
        "absence_type":    "SICK",
        "notified_at":     "4/10/2026 8:10:00 AM",
        "notified_by":     "agent_self_report",
        "notes":           "Absence covered by 61583018368573 (overtime, consented).",
        "replacement_assigned": "61583018368573",
    },
]

_path = os.path.join(DATA_DIR, "absence_notifications.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "notification_id", "agent_id", "absence_date", "absence_type",
        "notified_at", "notified_by", "notes", "replacement_assigned",
    ])
    w.writeheader()
    w.writerows(absence_rows)
print(f"  absence_notifications.csv     {len(absence_rows):>4} rows")


# ─────────────────────────────────────────────────────────────────────────────
# 9. OVERTIME CONSENT REGISTER
# ─────────────────────────────────────────────────────────────────────────────
# Records which agents have standing consent to be offered overtime / standby
overtime_rows = []
# Roughly 1/3 of agents on standby
for i, aid in enumerate(ALL_AGENTS):
    if i % 3 == 0:
        overtime_rows.append({
            "agent_id":       aid,
            "team":           team_of(aid),
            "consented":      True,
            "max_extra_hours_pw": 4,
            "consent_valid_from": "1/1/2026",
            "consent_valid_to":   "12/31/2026",
            "notes":          "Standing overtime consent — up to 4 extra hrs/week",
        })
    else:
        overtime_rows.append({
            "agent_id":       aid,
            "team":           team_of(aid),
            "consented":      False,
            "max_extra_hours_pw": 0,
            "consent_valid_from": "",
            "consent_valid_to":   "",
            "notes":          "",
        })

_path = os.path.join(DATA_DIR, "overtime_consent.csv")
with open(_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=[
        "agent_id", "team", "consented", "max_extra_hours_pw",
        "consent_valid_from", "consent_valid_to", "notes",
    ])
    w.writeheader()
    w.writerows(overtime_rows)
print(f"  overtime_consent.csv          {len(overtime_rows):>4} rows")


print()
print(f"All CSV files written to: {DATA_DIR}")
print()
print("Demo scenarios baked in:")
print("  Leave Grant  — GRANT (uid 1,2,9,10,11) | DENY:BALANCE (uid 3) | DENY:CAPACITY (uid 4) | DENY:BLACKOUT (uid 5)")
print("  Shift Swap   — APPROVE (uid 101,102) | DENY:SKILL_MISMATCH (uid 103) | DENY:COVERAGE_FLOOR (uid 105)")
print("  Replacement  — Sick call Apr 13 (agent 61581509267603), Emergency Apr 14 (agent 61581904917164)")
print("  Adherence    — scheduled_roster.csv provides start/end for all 20 agents × 3 days")
