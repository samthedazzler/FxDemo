# Operations Pillar — Data Requirements

> **Purpose:** Documents which data each Operations API needs, what is already available from
> the current CSV (`Agent_Breakdown_140426.csv`), and what must come from external systems
> before the limited-data endpoints can produce real decisions.

---

## Data Availability Summary

| Task | Endpoint | Data Status | Missing Data |
|------|----------|-------------|--------------|
| 1 | `/productive-hours` | ✅ LIVE | — |
| 2 | `/shrinkage-rate` | ✅ LIVE | — |
| 3 | `/anomaly-detection` | ✅ LIVE (partial score) | Adherence %, Quality %, Attendance % |
| 4 | `/shift-span` | ✅ LIVE | Scheduled start (for precise late-start) |
| 5 | `/occupancy` | ✅ LIVE | — |
| 6 | `/break-compliance` | ✅ LIVE | — |
| 7 | `/coverage-monitoring` | ✅ LIVE (counts only) | Required staff from WFM Capacity Planner |
| 8 | `/trend-analysis` | ✅ LIVE | — |
| 9 | `/leave-grant` | ⚠️ LIMITED_DATA | Leave entitlement, WFM allowance, blackout calendar |
| 10 | `/replacement-decisions` | ⚠️ LIMITED_DATA | Scheduled roster, skill matrix, absence notifications |
| 11 | `/shift-swap` | ⚠️ LIMITED_DATA | Scheduled roster, skill matrix, swap request queue |
| 12 | `/schedule-adherence` | ⚠️ LIMITED_DATA | Scheduled start/end times per agent |

---

## Current Data Source

**File:** `operations/Agent_Breakdown_140426.csv`  
**Coverage:** 3 days — 2026-04-12, 2026-04-13, 2026-04-14  
**Scope:** ~20 agents, Teleperformance-Dublin  
**Granularity:** Interval-level rows (30-min), one row per agent per status per interval

### Fields available in CSV

| Field | Used By Tasks |
|-------|--------------|
| Agent ID | All |
| Work Date | All |
| Team | All |
| Site | 4 |
| Status Group (OCC / CFT / NaN) | 1, 2, 3, 5, 7, 8 |
| Status Name (break, lunch, training…) | 2, 6 |
| OCC Minutes | 1, 2, 3, 5, 7, 8 |
| CFT Minutes | 2, 5, 7 |
| Break Minutes (from NaN status rows) | 2, 6 |
| Training Minutes (from NaN status rows) | 2 |
| Local Start Time (interval) | 4, 7 |
| Local End Time (interval) | 4, 7 |
| First Login (derived — earliest start per agent/day) | 4, 12 |
| Last Logout (derived — latest end per agent/day) | 4, 12 |

---

## Task 3 — Anomaly Detection: Partial Performance Score

**Partial score formula (implemented):**
```
partial_score = 0.40 × productivity_pct + 0.20 × (occupancy_pct ÷ 85 × 100)
                (weights rescaled to sum to 1.0 across available components)
```

**Full composite score formula (ops_task_2.pdf §5):**
```
composite_score = 0.40 × Productivity %
                + 0.30 × Schedule Adherence %   ← MISSING (Task 12 dependency)
                + 0.20 × Quality Score %         ← MISSING (QA system)
                + 0.10 × Attendance Score %      ← MISSING (HR roster)
```

**Missing data to complete composite score:**

| Component | Weight | Source System | Integration Required |
|-----------|--------|---------------|---------------------|
| Schedule Adherence % | 30% | WFM Schedule Builder | Task 12 (scheduled start/end) |
| Quality Score % | 20% | QA / call-monitoring system | QA platform API or feed |
| Attendance Score % | 10% | HR roster / leave records | HR attendance ledger |

---

## Task 7 — Coverage Monitoring: Required Staff

**What's missing:** `required_staff` per 30-min interval is not in the CSV. It is an
output of the WFM Capacity Planner (Erlang C staffing model based on forecast volume + AHT).

**Workaround (implemented):** Pass `?required_staff=N` as a query parameter.
This allows manual testing against a known headcount requirement.

**Production integration needed:**
- `GET /api/capacity/headcount-by-interval?date=YYYY-MM-DD` from the WFM Capacity Planner
- Returns required staff per 30-min slot based on Erlang C forecast
- Operations Coverage Monitoring can then call this automatically and compute
  `Interval Compliance % = (Actual OCC Staff / Required Staff) × 100`

---

## Task 9 — Leave Grant: Required Data Sources

### 1. Leave Entitlement Balances

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | string | Foreign key to Agent master |
| `leave_type` | enum | ANNUAL / SICK / PERSONAL / COMPASSIONATE |
| `entitlement_days` | float | Full-year allocation |
| `used_days` | float | Days taken YTD |
| `remaining_days` | float | Computed: entitlement − used |

**Source system:** HR / LeaveLedger  
**DB table:** `leave_ledger` (partially defined in `app/models/db.py` — `LeaveLedger`)  
**Status:** Table structure exists; population pipeline not yet built.

### 2. WFM Leave Allowance Schedule

| Field | Type | Notes |
|-------|------|-------|
| `team_id` | string | |
| `date` | date | |
| `max_concurrent_absent` | int | From Erlang headcount floor |

**Source system:** WFM Capacity Planner → `/api/capacity`  
**Derivation:** `floor(team_size × max_absence_pct)` where `max_absence_pct` is typically 10%.

### 3. Blackout Calendar

| Field | Type | Notes |
|-------|------|-------|
| `site` | string | |
| `blackout_start` | date | |
| `blackout_end` | date | |
| `reason` | string | PEAK_SEASON / MANDATORY_COVERAGE / COMPLIANCE |

**Source system:** Operations / HR calendar  
**DB:** Could be added as `BlackoutDate` model in `app/models/db.py`

### 4. Pending Leave Request Queue

| Field | Type | Notes |
|-------|------|-------|
| `request_id` | UUID | |
| `agent_id` | string | |
| `leave_type` | enum | |
| `start_date` | date | |
| `end_date` | date | |
| `status` | enum | PENDING / APPROVED / DENIED |

**Source system:** HR ticketing / leave management system

---

## Task 10 — Replacement Decisions: Required Data Sources

### 1. Scheduled Roster

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | string | |
| `schedule_date` | date | |
| `scheduled_start` | time | |
| `scheduled_end` | time | |
| `queue_assignment` | string | Which call queue agent is assigned to |

**Source system:** WFM Schedule Builder → `/api/schedule`

### 2. Skill / Queue Certification Matrix

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | string | |
| `queue_id` | string | |
| `certified` | bool | Can agent handle this queue? |
| `proficiency` | int | 1 (basic) – 5 (expert) |

**Source system:** HR / Training records

### 3. Absence Notifications

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | string | |
| `absence_date` | date | |
| `absence_type` | enum | SICK / EMERGENCY / APPROVED |
| `notified_at` | datetime | When Operations received the notification |

**Source system:** HR ticketing / absence management system

---

## Task 11 — Shift Swap: Required Data Sources

Same roster and skill matrix as Task 10, plus:

### Swap Request Queue

| Field | Type | Notes |
|-------|------|-------|
| `request_id` | UUID | |
| `agent_a_id` | string | Agent giving away their shift |
| `agent_b_id` | string | Agent taking agent A's shift |
| `agent_a_date` | date | Date agent A wants to swap away |
| `agent_b_date` | date | Date agent B wants to swap away |
| `status` | enum | PENDING / APPROVED / DENIED |
| `deny_reason` | string | Populated on denial |

### WFM Coverage Floor

Required staff minimum per date (same as Task 7).  
**Source:** WFM Capacity Planner → `/api/capacity`

---

## Task 12 — Schedule Adherence: Required Data Sources

### Scheduled Start / End Per Agent Per Day

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | string | |
| `schedule_date` | date | |
| `scheduled_start` | datetime | Agent's planned login time |
| `scheduled_end` | datetime | Agent's planned logout time |
| `scheduled_break_start` | datetime | When agent should take break |
| `scheduled_break_end` | datetime | When break should end |

**Source system:** WFM Schedule Builder → `/api/schedule`

**Why this unblocks adherence:**
```
Scheduled Minutes = (scheduled_end − scheduled_start) in minutes
Adherent Minutes  = minutes agent was in correct status during scheduled window
Adherence %       = (Adherent Minutes / Scheduled Minutes) × 100
```

Once scheduled start/end is available:
- Compare `first_login` vs `scheduled_start` → late-start delta
- Compare `last_logout` vs `scheduled_end` → early-departure delta
- Interval-by-interval status check against planned queue assignment

---

## Integration Roadmap

```
Phase 1 (current):   Tasks 1–8 live from CSV.
Phase 2 (next):      Connect WFM Schedule Builder (/api/schedule) → unblocks Tasks 7, 10, 11, 12.
Phase 3:             Connect HR Leave Ledger + blackout calendar → unblocks Task 9.
Phase 4:             Connect QA scoring + attendance ledger → completes Task 3 composite score.
```

---

*Generated from operations_task_1.pdf, operations_task_2.pdf, BEST WFM Reference Document v24.0.0.*
