# WFM SAAS — Functionalities Reference

> **Purpose:** This document describes the two core functional pillars — **Finance** and **Operations** — their internal structure, what each module produces, what data they require, and how they integrate with the Workforce Management (WFM) platform.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Finance Pillar (`finance_func/`)](#2-finance-pillar-finance_func)
   - [Folder Structure](#21-folder-structure)
   - [Endpoints](#22-endpoints)
   - [Services](#23-services)
   - [Billing Engine Pipeline](#24-billing-engine-pipeline)
   - [Preview Service](#25-preview-service)
   - [Data Requirements](#26-data-requirements)
   - [Outputs](#27-outputs)
3. [Operations Pillar (`operations/`)](#3-operations-pillar-operations)
   - [Folder Structure](#31-folder-structure)
   - [Data Layer](#32-data-layer-csv-loader)
   - [Live Tasks (1–8)](#33-live-tasks-18)
   - [Limited-Data Tasks (9–12)](#34-limited-data-tasks-912)
   - [Data Requirements](#35-data-requirements)
4. [WFM Integration Contract](#4-wfm-integration-contract)
   - [Finance ↔ WFM Contract](#41-finance--wfm-contract)
   - [Operations ↔ WFM Contract](#42-operations--wfm-contract)
5. [End-to-End Data Flow](#5-end-to-end-data-flow)
6. [Shared Infrastructure](#6-shared-infrastructure)
7. [Running the Application](#7-running-the-application)

---

## 1. Project Overview

**WFM_SAAS** is a FastAPI-based SaaS platform built on three integrated pillars:

| Pillar | Folder | Role |
|---|---|---|
| **Finance** | `finance_func/` | Agent-level billing engine — computes daily pay, leave deductions, min/max enforcement |
| **Operations** | `operations/` | Decision-support layer — 12 analytical tasks over interval-level agent activity |
| **WFM Core** | `wfm/`, `app/` | Workforce management — forecasting, scheduling, capacity planning, RTM, Erlang |

**Stack:** FastAPI 0.136.1 · SQLAlchemy 2.0.49 · Pydantic 2.13.4 · SQLite (`wfm_finance.db`) · Uvicorn 0.47.0

---

## 2. Finance Pillar (`finance_func/`)

### 2.1 Folder Structure

```
finance_func/
├── __init__.py
└── app/
    ├── __init__.py
    ├── routers/
    │   ├── __init__.py
    │   └── finance.py              # HTTP layer — 5 endpoints
    └── services/
        ├── __init__.py
        ├── finance_service.py      # Orchestrator — 7-step pipeline wiring
        ├── billing_engine.py       # Pure computation — deterministic pay calculation
        └── preview_service.py      # OT cost preview (synchronous, no DB write)
```

---

### 2.2 Endpoints

All routes are mounted under the `/finance` prefix.

#### `POST /finance/breakdown`
**WFM publishes a daily-finalized activity event; Finance returns the computed cost breakdown.**

| Direction | Field | Type | Description |
|---|---|---|---|
| **Input** | `agent_id` | `str` | Agent identifier |
| | `work_date` | `date` | The work date being finalized |
| | `productive_minutes` | `int` | OCC (on-call) minutes |
| | `available_minutes` | `int` | CFT (available) minutes |
| | `break_minutes` | `int` | Scheduled break minutes |
| | `training_minutes` | `int` | Training/meeting minutes |
| | `scheduled_minutes` | `int` | Contracted shift length |
| | `worked_minutes` | `int` | Actual time logged |
| | `overtime_minutes` | `int` | Explicit OT (optional; derived if 0) |
| | `is_holiday` | `bool` | Public holiday flag |
| | `night_minutes` | `int` | Minutes in night-differential window |
| **Query param** | `requested_leave_type` | `str?` | Pins which leave bucket to decrement |
| **Output** | `daily_gross` | `Decimal` | Today's computed gross pay |
| | `components` | `PayComponents` | Breakdown: regular, OT, holiday, night, leave pay |
| | `mtd_gross` | `Decimal` | Month-to-date accumulator |
| | `projected_monthly` | `Decimal` | (MTD / days_elapsed) × days_in_month |
| | `billing_status` | `str` | NORMAL / PENDING_APPROVAL / BLOCKED |

---

#### `POST /finance/breakdown/from-wfm-raw`
**Convenience wrapper for systems that send raw status maps rather than pre-aggregated minutes.**

| Direction | Field | Type | Description |
|---|---|---|---|
| **Input** | `agent_id` | `str` | Agent identifier |
| | `date` | `date` | Work date |
| | `status_minutes` | `dict[str, int]` | Raw status → minutes map (e.g. `{"chat": 120, "available": 60}`) |
| | `scheduled_minutes` | `int` | Contracted shift length |
| | `is_holiday` | `bool` | Public holiday flag |
| | `night_minutes` | `int` | Night-differential minutes |
| | `site` | `str` | Site identifier for holiday lookup |
| **Output** | Same as `/finance/breakdown` | — | Internally aggregates the status map then calls the same 7-step pipeline |

---

#### `POST /finance/preview`
**Synchronous OT cost preview — called by the WFM dashboard before a manager approves overtime. No database write.**

| Direction | Field | Type | Description |
|---|---|---|---|
| **Input** | `agent_id` | `str` | Agent identifier |
| | `date` | `date` | Proposed OT date |
| | `proposed_overtime_hours` | `float` | Hours of proposed OT |
| | `night_hours` | `float` | Night-window hours within that OT |
| | `is_holiday` | `bool` | Holiday flag |
| **Output** | `estimated_additional_cost` | `Decimal` | Cost of the proposed OT block |
| | `mtd_before` | `Decimal` | MTD gross before adding this OT |
| | `projected_total` | `Decimal` | MTD + estimated cost |
| | `cap_breach` | `bool` | True if projected > max_monthly_pay |
| | `floor_active` | `bool` | True if projected < min_monthly_pay |
| | `approval_recommendation` | `str` | APPROVE / APPROVE_WITH_CAUTION / BLOCK |
| | `stale_rate_card` | `bool` | True if rate card > 24 h old |

---

#### `GET /finance/breakdown/{agent_id}/{work_date}`
Returns the single persisted `FinancialBreakdown` record for one agent on one date.

#### `GET /finance/breakdown/{agent_id}`
Returns a list of `FinancialBreakdown` records. Accepts optional `start_date` and `end_date` query params.

#### `GET /finance/monthly/{agent_id}/{year}/{month}`
Returns the `MonthlyRollup` — the binding payroll number after min/max enforcement.

| Output Field | Description |
|---|---|
| `monthly_gross` | Raw sum of all daily_gross values |
| `monthly_pay` | After min/max enforcement — this is the payroll number |
| `days_counted` | Working days in the period |
| `component_breakdown` | Summed PayComponents |
| `min_max_status` | NONE / MIN_FLOOR_APPLIED / MAX_CAP_APPLIED |
| `alerts` | List of policy alerts (e.g. PENDING_APPROVAL_BLOCKS_CLOSE) |

---

### 2.3 Services

#### `finance_service.py` — Orchestrator

`process_breakdown(db, payload, requested_leave_type)` wires together all sub-services in the correct order:

1. Validate agent exists in Agent Master
2. Resolve holiday for the agent's site via Holiday Calendar
3. Persist / update raw `HourlyBreakdown` record (audit trail)
4. Call Leave Service → `resolve()` to consume leave balance
5. Fetch rate card snapshot via Rate Card Service
6. Call Billing Engine → `compute()` with all inputs
7. Persist `FinancialBreakdown` with content hash, write Audit Log entry

`monthly_rollup(db, agent_id, year, month)` performs month-close:
- Sums daily_gross for the period
- Re-applies min/max against the final monthly total
- Blocks close if any PENDING_APPROVAL records exist
- Returns `MonthlyRollup` with alert flags

---

#### `billing_engine.py` — Pure Computation

**Input dataclasses:**

| Dataclass | Key Fields |
|---|---|
| `HourlyInputs` | productive_minutes, available_minutes, break_minutes, training_minutes, scheduled_minutes, worked_minutes, overtime_minutes, is_holiday, night_minutes |
| `AgentRateInputs` | base_hourly_rate, overtime_multiplier, holiday_multiplier, night_differential, min_monthly_pay, max_monthly_pay, weekly_contracted_hours, currency, rate_card_version |
| `LeaveResolution` | is_absence_day, paid_from_balance_days, unpaid_days, leave_pay, billing_status, policy_applied, alerts, blocked_reason |

**Output dataclass:** `BillingResult` — includes daily_gross, MTD, projected monthly, PayComponents, min/max status, billing_status, provenance.

---

### 2.4 Billing Engine Pipeline

The engine implements a **deterministic 7-step pipeline** — given identical inputs it always returns the same output.

```
Step 1 — Classify Worked Hours
   regular_minutes  = min(worked_minutes, scheduled_minutes)
   overtime_minutes = max(0, worked_minutes − scheduled_minutes)
                      [or explicit WFM OT if provided]
   night_minutes    = direct from input
   holiday_minutes  = worked_minutes  IF is_holiday  ELSE 0

Step 2 — Leave Resolution (delegated to Leave Service)
   Determines: is_absence_day, leave_pay, billing_status

Step 3 — Apply Rate Multipliers
   Regular Pay  = (regular_min  / 60) × base_rate
   Overtime Pay = (overtime_min / 60) × base_rate × overtime_multiplier
   Holiday Pay  = (holiday_min  / 60) × base_rate × holiday_multiplier
   Night Pay    = (night_min    / 60) × base_rate × night_differential
   [Precision: 4 decimal places — Decimal arithmetic, no floats]

Step 4 — Sum & Accrue
   daily_gross = regular_pay + overtime_pay + holiday_pay + night_premium + leave_pay

Step 5 — Persist HourlyBreakdown + FinancialBreakdown (via finance_service)

Step 6 — Apply Min / Max (at month-close)
   monthly_gross < min_pay  →  monthly_pay = min_pay   [MIN_FLOOR_APPLIED]
   monthly_gross > max_pay  →  monthly_pay = max_pay   [MAX_CAP_APPLIED]
   Otherwise               →  monthly_pay = monthly_gross

Step 7 — Return BillingResult with full provenance
```

---

### 2.5 Preview Service

`preview_service.py` implements the OT approval workflow (no database write):

1. Fetch agent + current rate card snapshot
2. Flag stale rate card (>24 h per Section 10 mitigation)
3. Compute `estimated_cost`:
   - If holiday: `rate_per_hour = base × holiday_multiplier`
   - Else: `rate_per_hour = base × overtime_multiplier`
   - `estimated_cost = (ot_hours × rate_per_hour) + (night_hours × base × night_differential)`
4. Fetch MTD already accrued from `FinancialBreakdown`
5. Compute `projected = MTD + estimated_cost`
6. Check against min / max → set `cap_breach`, `floor_active`
7. Return `approval_recommendation`:
   - `BLOCK` if cap_breach (uncompensated OT alert)
   - `APPROVE_WITH_CAUTION` if is_holiday
   - `APPROVE` otherwise

---

### 2.6 Data Requirements

| Data Source | What Finance Needs | Where It Comes From |
|---|---|---|
| **Agent Master** | Agent exists, site assignment, metadata | `app/routers/agents` — HR / onboarding feed |
| **Rate Card** | base_hourly_rate, overtime_multiplier, holiday_multiplier, night_differential, min/max monthly pay | `app/routers/rate-card` — HR / Payroll system |
| **Holiday Calendar** | Is a given date a public holiday for a given site? | `app/routers/holidays` — HR / Payroll system |
| **Leave Ledger** | Agent leave balance per type; consume balance on absence | `app/routers/leaves` — HR / Leave management |
| **WFM Activity** | Hourly breakdown of OCC / CFT / break / training / scheduled / worked / OT / night minutes | **WFM platform publishes via POST `/finance/breakdown`** |

---

### 2.7 Outputs

| Record | Persisted In | Consumed By |
|---|---|---|
| `HourlyBreakdown` | `wfm_finance.db` | Audit trail; re-processing |
| `FinancialBreakdown` | `wfm_finance.db` | Payroll export; month-close; OT preview |
| `AuditLog` | `wfm_finance.db` | Compliance; reconciliation |
| `MonthlyRollup` | Computed on demand | Payroll system (binding payroll number) |

---

## 3. Operations Pillar (`operations/`)

### 3.1 Folder Structure

```
operations/
├── __init__.py
├── main.py                          # FastAPI sub-application; router registration
├── README.md                        # API quick-reference
├── DATA_REQUIREMENTS.md             # Missing data spec for Tasks 9–12
├── Agent_Breakdown_140426.csv       # Sample dataset (3 days, ~20 agents)
├── services/
│   ├── __init__.py
│   └── csv_loader.py                # Shared data layer — all tasks read from here
└── routers/
    ├── __init__.py
    ├── productive_hours.py          # Task 1
    ├── shrinkage.py                 # Task 2
    ├── anomaly_detection.py         # Task 3
    ├── shift_span.py                # Task 4
    ├── occupancy.py                 # Task 5
    ├── break_compliance.py          # Task 6
    ├── coverage_monitoring.py       # Task 7
    ├── trend_analysis.py            # Task 8
    ├── leave_grant.py               # Task 9  (LIMITED_DATA stub)
    ├── replacement_decisions.py     # Task 10 (LIMITED_DATA stub)
    ├── shift_swap.py                # Task 11 (LIMITED_DATA stub)
    └── schedule_adherence.py        # Task 12 (LIMITED_DATA partial)
```

---

### 3.2 Data Layer (`csv_loader.py`)

All 12 Operations tasks share a single data-access service that reads `Agent_Breakdown_140426.csv`.

**CSV Coverage:**
- **Dates:** 2026-04-12, 2026-04-13, 2026-04-14 (3 days)
- **Agents:** ~20 agents, Teleperformance Dublin
- **Granularity:** Interval-level rows (30-minute buckets)
- **Columns:** Agent Id, Status, Status Group, time_in_interval_m, Local Interval Start, Local Interval End, Local Start Time, Local End Time, SRT Team, Vendor Site

**Status Classification (BEST WFM §2.2):**

| Category | Statuses Mapped |
|---|---|
| **OCC** (Transaction) | chat, after_contact_work, email, email_backlog |
| **CFT** (Available) | available |
| **Break** (In-Office Shrinkage) | break, lunch |
| **Training** (In-Office Shrinkage) | facebook_training_meeting, meeting, coaching, production_training, administrative_task |

**Key Aggregates Computed (BEST WFM §1.4):**

| Metric | Formula |
|---|---|
| Occupancy % | `OCC_min / (OCC + CFT) × 100` |
| Productivity % | `OCC_min / Present_min × 100` |
| In-Office Shrinkage % | `(Break + Training) / Present × 100` |
| Utilisation % | `(OCC + CFT) / Present × 100` |
| Present Minutes | `OCC + CFT + Break + Training` |
| Shift Span Hours | `(Last_Activity_End − First_Login)` in hours |

**Dataclasses exposed:**
- `RawRow` — one CSV record
- `AgentDayAggregate` — per (agent, date) summary with all derived metrics
- `IntervalAggregate` — per (date, 30-min interval) summary with agent counts

---

### 3.3 Live Tasks (1–8)

All live-task routes are prefixed `/api/operations/`.

---

#### Task 1 — Productive Hours
**`GET /api/operations/productive-hours?query_date=YYYY-MM-DD[&agent_id=X]`**

**What it returns:**
- Per-agent: OCC minutes, productive hours, present hours, productivity %, flag if < 85%
- Team summary: total agents, team totals and averages

**Formula:** `Productive Hours = OCC_min / 60` · `Productivity % = OCC / Present × 100`

**Flag threshold:** Productivity % < 85% → status = `BELOW_THRESHOLD`

**WFM use case:** Identify underperforming agents for coaching; feed daily KPI dashboard.

---

#### Task 2 — Shrinkage Rate
**`GET /api/operations/shrinkage-rate?query_date=YYYY-MM-DD[&agent_id=X]`**

**What it returns:**
- Per-agent: break minutes, training minutes, total shrinkage minutes, shrinkage %, status
- Team summary: avg shrinkage %, optimal target %, required seats factor

**Formula:** `In-Office Shrinkage % = (Break + Training) / Present × 100`
**Required Seats Factor:** `1 / (1 − shrinkage_rate)` — used by WFM Capacity Planner

**Flag thresholds:** > 20% → HIGH · < 5% → LOW_BREAK · otherwise → OK

**WFM use case:** Feed shrinkage % into Erlang capacity model; detect break-policy violations before they become legal issues.

---

#### Task 3 — Anomaly Detection
**`GET /api/operations/anomaly-detection?query_date=YYYY-MM-DD`**

**What it returns:**
- Per-agent: occupancy %, productivity %, Z-score vs team mean, flags, recommended action, partial performance score
- Disappeared agents: agents present on Day 1 who do not appear on later dates
- Team summary: flagged count, mean/std occupancy

**Flags:**
| Flag | Condition |
|---|---|
| PRODUCTIVITY_BELOW_85 | productivity_pct < 85% |
| OCCUPANCY_BELOW_75 | occupancy_pct < 75% |
| Z_SCORE_CRITICAL | z_score < −2.0 |

**Partial Performance Score (ops_task_2.pdf §5):**
```
partial_score = 0.40 × Productivity % + 0.15 × Occupancy %
Missing components: Adherence (30%), Quality (20%), Attendance (10%)
```

**Recommended action:** `Coaching` if any flag raised · `Monitor` otherwise

**WFM use case:** Trigger automated coaching assignment in HR system; surface disappearance events for attendance follow-up.

---

#### Task 4 — Shift Span & Attendance
**`GET /api/operations/shift-span?query_date=YYYY-MM-DD[&agent_id=X]`**

**What it returns:**
- Per-agent: first login, last logout, shift span hours, present hours, attendance flags
- Team summary: agents present, agents flagged

**Flags:**
| Flag | Condition |
|---|---|
| LATE_START | First login > 15 min after earliest interval start |
| SHORT_SHIFT | Shift span < 4.0 hours |
| MULTI_FLAG | Both conditions |

**WFM use case:** Attendance register; trigger punctuality alerts; feed schedule adherence baseline.

---

#### Task 5 — OCC / CFT Occupancy
**`GET /api/operations/occupancy?query_date=YYYY-MM-DD[&agent_id=X]`**

**What it returns:**
- Per-agent: OCC minutes, CFT minutes, production minutes, occupancy %, availability rate %, utilisation %, occupancy status, routing flag
- Team summary: avg occupancy, avg utilisation, agents low / overloaded

**Occupancy Status:**
| Band | Condition | Meaning |
|---|---|---|
| LOW | < 75% | Routing or skill-match issue |
| HEALTHY | 75–85% | Target range (BEST WFM) |
| HIGH | > 85% | Burnout risk |

**WFM use case:** Real-time management (RTM) alerting; routing rule adjustment; capacity rebalancing.

---

#### Task 6 — Break Compliance Audit
**`GET /api/operations/break-compliance?query_date=YYYY-MM-DD[&agent_id=X]`**

**What it returns:**
- Per-agent: shift span hours, break minutes, lunch flag, violation type, compliance status, legal risk level, supervisor action required
- Team summary: compliant count, violations, high-risk violations

**Legal rules — Irish Working Time Act 1997:**
| Violation | Condition | Risk |
|---|---|---|
| VIOLATION_6H | Shift ≥ 6h AND break < 30 min | HIGH |
| VIOLATION_4H | Shift ≥ 4.5h AND break < 15 min | MEDIUM |
| ZERO_BREAK_FULL_SHIFT | break = 0 AND present ≥ 1h | MEDIUM |

**WFM use case:** Automated compliance audit; generate supervisor action list; feed HR legal-risk report.

---

#### Task 7 — Coverage Monitoring
**`GET /api/operations/coverage-monitoring?query_date=YYYY-MM-DD[&required_staff=N]`**

**What it returns:**
- Per 30-min interval: active agents, OCC agents, CFT agents, OCC/CFT minutes, coverage gap, interval compliance %, status
- Summary: peak/min active agents, intervals understaffed, data limitation note

**Formula (ops_task_2.pdf §10):**
```
Interval Compliance % = (Actual OCC Staff / Required Staff) × 100
Coverage Gap = max(0, Required Staff − Active Agents)
```

**Note:** Required staff headcount is **not in the CSV** — it must be passed as the `required_staff` query param or sourced from the WFM Capacity Planner / Erlang output.

**WFM use case:** RTM coverage dashboard; intra-day reforecasting trigger; SLA breach alerting.

---

#### Task 8 — Trend Analysis (3-Day)
**`GET /api/operations/trend-analysis[?agent_id=X]`**

**What it returns:**
- Per-agent: daily metrics for all 3 dates, linear regression slopes for occupancy / productivity / shrinkage, trend classification, overall alert level, coaching priority flag
- Summary: agents declining occupancy, agents declining productivity, coaching-priority count

**Algorithm:** Linear regression over 3 days
```
slope = Σ((xi − x̄)(yi − ȳ)) / Σ((xi − x̄)²)
where xi = day index {0,1,2}, yi = metric value
```

**Trend classification:**
| Classification | Condition |
|---|---|
| DECLINING | slope < −1.0 %/day |
| IMPROVING | slope > +1.0 %/day |
| STABLE | |slope| ≤ 1.0 |
| INSUFFICIENT_DATA | < 2 data points |

**Alert levels:**
| Level | Condition |
|---|---|
| CRITICAL | Occupancy DECLINING AND Productivity DECLINING |
| WARNING | One of (Occupancy, Productivity) DECLINING OR Shrinkage IMPROVING |
| WATCH | Any remaining DECLINING trend |
| OK | No declining trends |

**WFM use case:** Weekly performance review automation; proactive coaching queue; early-warning system before SLA impact.

---

### 3.4 Limited-Data Tasks (9–12)

These endpoints return **stub responses** that specify exactly what data is needed and what the decision logic will be. They are ready to go live once the missing data feeds are connected.

---

#### Task 9 — Leave Grant Decisions
**`GET /api/operations/leave-grant[?agent_id=X[&request_date=YYYY-MM-DD]]`**

**Decision logic (when data available):**
1. Agent has sufficient leave balance of the requested type
2. Team not at capacity (concurrent absences < WFM max allowed)
3. Date not in blackout calendar
→ All pass → GRANT · Any fail → DENY with specific reason

**Missing data required:**
- Leave entitlement balances per agent per type (HR system)
- WFM leave allowance schedule (Erlang-derived max concurrent absences per date)
- Blackout calendar (peak season, mandatory coverage dates)
- Pending leave request queue
- Currently approved absences per date

---

#### Task 10 — Replacement Decisions
**`GET /api/operations/replacement-decisions[?absent_agent_id=X[&absence_date=YYYY-MM-DD]]`**

**Decision logic (when data available):**
1. Identify absent agent's scheduled queues and skill set
2. Find available agents (scheduled but occupancy < 80%)
3. Filter by skill match
4. Check replacement won't breach 48h/week (Irish Working Time Act)
5. Rank candidates, assign first eligible; if none → escalate

**Ranking formula:**
```
score = (1 − occupancy_pct / 100) × 0.6 + seniority_score × 0.4
```

**Missing data required:**
- Scheduled roster (WFM Schedule Builder)
- Skill / queue matrix (HR)
- Real-time absence notifications (HR ticketing / call-out system)
- Overtime consent records
- Rolling weekly hours accumulation per agent

---

#### Task 11 — Shift Swap Management
**`GET /api/operations/shift-swap[?agent_a=X[&agent_b=Y[&agent_a_date=D1[&agent_b_date=D2]]]]`**

**Validation checks (all must pass for APPROVE):**
1. Both agents are scheduled on their respective target dates
2. Skill cross-coverage — Agent A can cover Agent B's queue and vice versa
3. Projected weekly hours ≤ 48h for both agents
4. Neither date drops below the WFM coverage floor

**Missing data required:**
- Scheduled roster (WFM Schedule Builder)
- Skill / queue matrix (HR)
- Swap request queue
- WFM coverage floor (Erlang-derived minimum staffing)
- Rolling weekly hours per agent (derivable from CSV once full-week data is loaded)

---

#### Task 12 — Schedule Adherence
**`GET /api/operations/schedule-adherence?query_date=YYYY-MM-DD[&agent_id=X]`**

**Status:** Partial — actual activity data available; scheduled data missing.

**Formula (ops_task_2.pdf §9):**
```
Schedule Adherence % = (Adherent Minutes / Scheduled Minutes) × 100
Adherent Minutes = minutes in correct status during scheduled window
                   (OCC/CFT when scheduled on-phones; break when scheduled on-break)
```

**Thresholds:** ≥ 90% target · < 85% supervisor review · < 75% manager escalation

**Available in CSV:** Actual first login, last logout, actual OCC / CFT / break minutes, interval-level status

**Missing data required:**
- Scheduled start / end time per agent per day (WFM Schedule Builder)
- Scheduled break windows
- Interval-level scheduled queue assignment

---

### 3.5 Data Requirements

| Task | Currently Available | Missing — Needed From |
|---|---|---|
| Tasks 1–8 | CSV activity data (3 days) | Nothing — fully live |
| Task 7 (Coverage) | Actual staffing per interval | Required headcount → WFM Capacity Planner |
| Task 9 (Leave Grant) | Nothing relevant | HR leave balances, WFM allowance schedule, blackout calendar |
| Task 10 (Replacement) | Actual activity | Roster, skill matrix, absence notifications, weekly hours |
| Task 11 (Shift Swap) | Actual activity | Roster, skill matrix, coverage floor, weekly hours |
| Task 12 (Adherence) | Actual activity | Scheduled start/end times, break windows (WFM Schedule Builder) |

---

## 4. WFM Integration Contract

### 4.1 Finance ↔ WFM Contract

This is the formal interface described in **WFM_Finance_Integration_Design.pdf v0.1 Section 7**.

#### WFM → Finance (daily publish)
After a shift is finalized, WFM calls:

```http
POST /finance/breakdown
Content-Type: application/json

{
  "agent_id": "AGT-001",
  "work_date": "2026-04-14",
  "productive_minutes": 240,
  "available_minutes": 60,
  "break_minutes": 30,
  "training_minutes": 15,
  "scheduled_minutes": 480,
  "worked_minutes": 495,
  "overtime_minutes": 15,
  "is_holiday": false,
  "night_minutes": 0
}
```

Finance persists the breakdown, computes pay, and returns `BillingResponse`. The `billing_status` field drives WFM dashboard indicators.

#### WFM → Finance (OT approval gate)
Before a manager approves overtime, WFM calls:

```http
POST /finance/preview
Content-Type: application/json

{
  "agent_id": "AGT-001",
  "date": "2026-04-14",
  "proposed_overtime_hours": 1.5,
  "night_hours": 0.0,
  "is_holiday": false
}
```

Finance returns `approval_recommendation`. WFM uses this to block, warn, or allow the approval.

#### Finance → WFM (month-close)
WFM fetches the binding payroll number:

```http
GET /finance/monthly/{agent_id}/{year}/{month}
```

Returns `MonthlyRollup.monthly_pay` — the number sent to payroll after min/max enforcement.

---

### 4.2 Operations ↔ WFM Contract

Operations tasks consume WFM-published activity data (via the CSV today; via a live feed in production) and return decision support that drives WFM actions.

| Operations Output | WFM Action |
|---|---|
| Task 1 — Productivity % per agent | Feed KPI dashboard; trigger coaching |
| Task 2 — Shrinkage % | Feed into Erlang / capacity model as shrinkage input |
| Task 3 — Anomaly flags | Trigger HR coaching workflow; surface disappearances |
| Task 4 — Attendance flags | Attendance register; punctuality report |
| Task 5 — Occupancy status | RTM routing rule adjustment |
| Task 6 — Break compliance | Legal risk report; supervisor action list |
| Task 7 — Coverage gaps | RTM understaffing alerts; intra-day reforecasting |
| Task 8 — Trend slopes | Weekly review; proactive coaching queue |
| Task 9 — Leave grant decision | WFM posts leave request → Operations returns GRANT/DENY |
| Task 10 — Replacement pick | WFM posts absence event → Operations returns candidate |
| Task 11 — Swap validation | WFM posts swap request → Operations returns APPROVE/DENY |
| Task 12 — Adherence % | Schedule adherence dashboard; supervisor escalation |

---

## 5. End-to-End Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    WFM Platform                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Forecast │  │ Capacity │  │ Schedule │  │    RTM    │  │
│  │  Studio  │  │ Planner  │  │ Builder  │  │ Dashboard │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │             │             │               │        │
└───────┼─────────────┼─────────────┼───────────────┼────────┘
        │             │             │               │
        │    Shrinkage│    Required │   Scheduled   │  Activity
        │    input    │    headcount│   roster      │  feed (CSV→live)
        ▼             ▼             ▼               ▼
┌───────────────────────────────────────────────────────────────────┐
│                  OPERATIONS PILLAR                                │
│  Tasks 1–8 (LIVE)            Tasks 9–12 (needs more data)        │
│  ├─ Task 1: Productive Hours  ├─ Task 9:  Leave Grant             │
│  ├─ Task 2: Shrinkage Rate    ├─ Task 10: Replacement Decisions   │
│  ├─ Task 3: Anomaly Detection ├─ Task 11: Shift Swap              │
│  ├─ Task 4: Shift Span        └─ Task 12: Schedule Adherence      │
│  ├─ Task 5: OCC/CFT Occupancy                                     │
│  ├─ Task 6: Break Compliance                                      │
│  ├─ Task 7: Coverage Monitoring                                   │
│  └─ Task 8: Trend Analysis                                        │
└───────────────────────────────────────────────────────────────────┘
        │
        │  Daily finalized activity (POST /finance/breakdown)
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                   FINANCE PILLAR                                  │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 7-Step Billing Engine                                       │ │
│  │  1. Classify hours (regular / OT / holiday / night)        │ │
│  │  2. Resolve leave (balance deduction, leave_pay)           │ │
│  │  3. Apply rate multipliers                                 │ │
│  │  4. Sum daily gross                                        │ │
│  │  5. Persist + audit log                                    │ │
│  │  6. Min/max enforcement (at month-close)                   │ │
│  │  7. Return BillingResult with full provenance              │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  Agent Master    │   │  Rate Card   │   │  Leave Ledger    │  │
│  │  Holiday Cal.    │   │  (versioned) │   │  Audit Log       │  │
│  └──────────────────┘   └──────────────┘   └──────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
        │
        │  monthly_pay (binding payroll number)
        ▼
   Payroll System
```

---

## 6. Shared Infrastructure

### Database — `wfm_finance.db` (SQLite)

| Table | Owned By | Purpose |
|---|---|---|
| `agents` | HR / Agent Master | Agent metadata, site assignment |
| `rate_cards` | Finance | Versioned pay rates per agent |
| `holiday_calendars` | Finance | Public holidays per site |
| `leave_ledgers` | Finance | Leave balance tracking per agent per type |
| `hourly_breakdowns` | Finance | Raw WFM input (audit trail) |
| `financial_breakdowns` | Finance | Computed daily pay record |
| `audit_logs` | Finance | Immutable event log |

All tables are created on startup via `Base.metadata.create_all()` in `app/main.py`.

### HTTP Routers (from `app/main.py`)

| Prefix | Module | Purpose |
|---|---|---|
| `/finance` | `finance_func.app.routers.finance` | Finance billing endpoints |
| `/agents` | `app.routers.agents` | Agent Master CRUD |
| `/leaves` | `app.routers.leaves` | Leave Ledger CRUD |
| `/rate-card` | `app.routers.rate_card` | Rate Card management |
| `/holidays` | `app.routers.holidays` | Holiday Calendar management |
| `/reconciliation` | `app.routers.reconciliation` | Nightly reconciliation |
| `/status-mapping` | `app.routers.status_mapping` | Status → pay category map |
| `/audit` | `app.routers.audit` | Audit log queries |
| `/ingest` | `app.routers.ingest` | CSV ingest |
| `/api/dashboard` | `wfm.routers` | WFM KPI dashboard |
| `/api/forecast` | `wfm.routers` | Forecast Studio |
| `/api/capacity` | `wfm.routers` | Capacity Planner |
| `/api/schedule` | `wfm.routers` | Schedule Builder |
| `/api/rtm` | `wfm.routers` | Real-time Management |
| `/api/erlang` | `wfm.routers` | Erlang Calculator |
| `/api/gm` | `wfm.routers` | GM Estimator |
| `/api/operations` | `operations.routers` | Operations Tasks 1–12 |

### Health Check

```http
GET /health
→ { "status": "ok", "service": "<app_name>", "version": "<app_version>" }
```

---

## 7. Running the Application

### Install dependencies
```bash
pip install -r requirements.txt
```

### Start the server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Interactive API docs
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key environment variables (via `.env` or shell)

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | WFM SAAS | Application name |
| `APP_VERSION` | 0.1.0 | Version string |
| `DATABASE_URL` | `sqlite:///./wfm_finance.db` | SQLAlchemy connection string |

---

*Reference documents: WFM_Finance_Integration_Design.pdf v0.1 · operations_task_1.pdf · operations_task_2.pdf · BEST WFM Reference v24.0.0 · Irish Working Time Act 1997*
