# Operations Pillar — API Reference

> **Role:** The Operations pillar is the decision-making layer that sits above WFM and Finance.
> WFM calculates capacity; Finance calculates cost; Operations decides what to *do*:
> who gets leave, who needs coaching, who covers an absent colleague, whether coverage SLA
> is being met, and whether agents are working when they're supposed to.
>
> **Source documents:** `operations_task_1.pdf`, `operations_task_2.pdf`, `BEST WFM Reference v24.0.0`  
> **Data source:** `operations/Agent_Breakdown_140426.csv` (3 days: Apr 12–14 2026, ~20 agents)  
> **Base URL:** `/api/operations`  
> **Entry point:** `operations/main.py`

---

## Quick Reference

| # | Endpoint | Status | Description |
|---|----------|--------|-------------|
| 1 | `GET /productive-hours` | ✅ LIVE | Daily OCC hours + Productivity % per agent |
| 2 | `GET /shrinkage-rate` | ✅ LIVE | In-office shrinkage rate (BEST WFM formula) |
| 3 | `GET /anomaly-detection` | ✅ LIVE (partial) | Z-score outliers + underperformer flags |
| 4 | `GET /shift-span` | ✅ LIVE | Shift span, late-start & short-shift flags |
| 5 | `GET /occupancy` | ✅ LIVE | OCC/CFT breakdown + occupancy status |
| 6 | `GET /break-compliance` | ✅ LIVE | Irish Working Time Act 1997 break audit |
| 7 | `GET /coverage-monitoring` | ✅ LIVE | 30-min interval active agent counts |
| 8 | `GET /trend-analysis` | ✅ LIVE | 3-day linear trend per agent |
| 9 | `GET /leave-grant` | ⚠️ LIMITED | Leave grant decision logic + data spec |
| 10 | `GET /replacement-decisions` | ⚠️ LIMITED | Absence replacement logic + data spec |
| 11 | `GET /shift-swap` | ⚠️ LIMITED | Shift swap validation logic + data spec |
| 12 | `GET /schedule-adherence` | ⚠️ LIMITED | Partial actual data; full adherence blocked |

---

## Task 1 — Daily Productive Hours

**Endpoint:** `GET /api/operations/productive-hours?query_date=YYYY-MM-DD`  
**File:** `operations/routers/task1_productive_hours.py`  
**Reference:** `operations_task_1.pdf §1`

### Formulas

```
Productive Hours   = OCC Minutes / 60
Productivity %     = OCC Minutes / Present Minutes × 100     (BEST WFM §1.4)
Present Minutes    = OCC Minutes + CFT Minutes + Break Minutes + Training Minutes
```

### Thresholds

| Condition | Flag |
|-----------|------|
| Productivity % < 85% | `productivity_flag = true` |

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `productive_hours` | float | OCC time in hours |
| `productivity_pct` | float | OCC / Present × 100 |
| `occ_minutes` | float | Raw OCC minutes |
| `present_hours` | float | Total present time |
| `productivity_flag` | bool | True if < 85% |

---

## Task 2 — Shrinkage Rate

**Endpoint:** `GET /api/operations/shrinkage-rate?query_date=YYYY-MM-DD`  
**File:** `operations/routers/task2_shrinkage.py`  
**Reference:** `operations_task_1.pdf §2`, `BEST WFM §1.4`

### Formulas

```
In-Office Shrinkage %  = Shrinkage Minutes / Present Minutes × 100

Shrinkage Minutes      = Break Minutes + Training Minutes
Present Minutes        = OCC + CFT + Shrinkage Minutes

Required Seats Factor  = 1 / (1 − shrinkage_rate)
```

> **Note:** `operations_task_1.pdf §2` explicitly flags `Break+Lunch / Total Logged` as
> incorrect. The BEST WFM definition uses Present Minutes as the denominator.

### Thresholds

| Condition | Flag |
|-----------|------|
| Shrinkage % > 35% | `high_shrinkage = true` |

---

## Task 3 — Anomaly Detection

**Endpoint:** `GET /api/operations/anomaly-detection?query_date=YYYY-MM-DD`  
**File:** `operations/routers/task3_anomaly_detection.py`  
**Reference:** `operations_task_1.pdf §3`, `operations_task_2.pdf §5`

### Formulas

**Z-score:**
```
z = (agent_occupancy_pct − team_mean_occ) / team_std_occ
Flag: z < −2.0  →  statistical outlier
```

**Partial Composite Performance Score (full score requires QA + Adherence data):**
```
partial_score = 0.40 × Productivity %
              + 0.20 × (Occupancy % / 85 × 100)   [proxy only]

Full formula (ops_task_2.pdf §5):
full_score = 0.40 × Productivity %
           + 0.30 × Schedule Adherence %
           + 0.20 × Quality Score %
           + 0.10 × Attendance Score %
```

### Rule-Based Flags

| Rule | Condition |
|------|-----------|
| `PRODUCTIVITY_LOW` | Productivity % < 85% |
| `OCCUPANCY_LOW` | Occupancy % < 75% |
| `Z_SCORE_OUTLIER` | Z-score < −2.0 |
| `DISAPPEARED` | Agent present on some dates, absent on others |

---

## Task 4 — Shift Span & Attendance

**Endpoint:** `GET /api/operations/shift-span?query_date=YYYY-MM-DD`  
**File:** `operations/routers/task4_shift_span.py`  
**Reference:** `operations_task_1.pdf §4`

### Formulas

```
Shift Span Hours = (Last Activity End − First Activity Start) in hours
```

### Thresholds

| Flag | Condition |
|------|-----------|
| `LATE_START` | First login > 15 min after earliest interval of the day |
| `SHORT_SHIFT` | Shift span < 4.0 hours |
| `MULTI_FLAG` | Both above conditions |

---

## Task 5 — OCC/CFT Occupancy Breakdown

**Endpoint:** `GET /api/operations/occupancy?query_date=YYYY-MM-DD`  
**File:** `operations/routers/task5_occupancy.py`  
**Reference:** `operations_task_1.pdf §5`, `operations_task_2.pdf §3`, `BEST WFM §1.4`

### Formulas

```
Occupancy %          = OCC Minutes / (OCC + CFT) Minutes × 100
Availability Rate %  = CFT Minutes / (OCC + CFT) Minutes × 100
Utilisation %        = Production Hours / Present Hours × 100

Production Minutes   = OCC + CFT
Present Minutes      = OCC + CFT + Shrinkage
```

### Thresholds

| Status | Condition |
|--------|-----------|
| `LOW` | Occupancy % < 75% — likely routing/skill issue |
| `HEALTHY` | 75% ≤ Occupancy % ≤ 85% |
| `HIGH` | Occupancy % > 85% — burnout risk (BEST WFM limit) |

`routing_flag = true` when status = `LOW`.

---

## Task 6 — Break Compliance Audit

**Endpoint:** `GET /api/operations/break-compliance?query_date=YYYY-MM-DD`  
**File:** `operations/routers/task6_break_compliance.py`  
**Reference:** `operations_task_1.pdf §6`, Irish Organisation of Working Time Act 1997

### Legal Rules

```
VIOLATION_6H:          shift_span_hours >= 6.0  AND  break_minutes < 30   → HIGH risk
VIOLATION_4H:          shift_span_hours >= 4.5  AND  break_minutes < 15   → MEDIUM risk
ZERO_BREAK_FULL_SHIFT: break_minutes == 0        AND  present_hours >= 1   → MEDIUM risk
```

> This is a **mandatory legal compliance** check. HIGH risk violations require
> immediate supervisor action. Finance exposure: labour law penalties.

---

## Task 7 — Coverage Monitoring (30-min Intervals)

**Endpoint:** `GET /api/operations/coverage-monitoring?query_date=YYYY-MM-DD[&required_staff=N]`  
**File:** `operations/routers/task7_coverage_monitoring.py`  
**Reference:** `operations_task_1.pdf §7`, `operations_task_2.pdf §10`

### Formulas

```
Interval Compliance % = (Actual OCC Staff / Required Staff) × 100
Coverage Gap          = max(0, Required Staff − Active Agents)
```

> `required_staff` is **not in the CSV**. It comes from the WFM Capacity Planner
> (Erlang C model). Pass it as `?required_staff=N` for manual testing.
> Without it, only active agent counts are returned.

### Status Values

| Status | Condition |
|--------|-----------|
| `SUFFICIENT` | Coverage gap = 0 |
| `UNDERSTAFFED` | Coverage gap > 0 |
| `UNKNOWN` | `required_staff` not provided |

---

## Task 8 — Trend Analysis

**Endpoint:** `GET /api/operations/trend-analysis[?agent_id=X]`  
**File:** `operations/routers/task8_trend_analysis.py`  
**Reference:** `operations_task_1.pdf §8`

### Algorithm

**Linear regression slope over 3 days:**
```
slope = Σ((xᵢ − x̄)(yᵢ − ȳ)) / Σ((xᵢ − x̄)²)

where: xᵢ = day index (0, 1, 2), yᵢ = metric value on day i
```

**Trend classification:**
```
slope < −1.0 %/day  →  DECLINING
slope > +1.0 %/day  →  IMPROVING
|slope| ≤ 1.0       →  STABLE
< 2 data points     →  INSUFFICIENT_DATA
```

**Alert levels:**
```
CRITICAL: Occupancy DECLINING and Productivity DECLINING
WARNING:  One of (Occupancy, Productivity) DECLINING, or Shrinkage IMPROVING
WATCH:    Any remaining DECLINING trend
OK:       No declining trends
```

`coaching_priority = true` if `occupancy_trend == DECLINING OR productivity_trend == DECLINING`

> **Statistical note:** 3 data points give only indicative trends. BEST WFM §3.4 recommends
> 2–4 week rolling windows for production use.

---

## Task 9 — Leave Grant Decisions ⚠️ LIMITED_DATA

**Endpoint:** `GET /api/operations/leave-grant`  
**File:** `operations/routers/task9_leave_grant.py`  
**Reference:** `operations_task_1.pdf §9`

### Decision Logic (when data is available)

```
Step 1: agent.leave_balance[type] >= requested_days  →  else DENY: INSUFFICIENT_BALANCE
Step 2: concurrent_absent(team, date) < wfm_max_absent  →  else DENY: TEAM_AT_CAPACITY
Step 3: request_date NOT IN blackout_calendar  →  else DENY: BLACKOUT_DATE
→ All pass: GRANT
```

### Missing Data

- Leave entitlement balances per agent
- WFM leave allowance schedule (Erlang-derived max concurrent absences)
- Blackout calendar
- Pending leave request queue

See `DATA_REQUIREMENTS.md §Task 9`.

---

## Task 10 — Replacement Decisions ⚠️ LIMITED_DATA

**Endpoint:** `GET /api/operations/replacement-decisions`  
**File:** `operations/routers/task10_replacement_decisions.py`  
**Reference:** `operations_task_1.pdf §10`

### Decision Logic (when data is available)

```
1. Identify absent agent's scheduled queues for the day
2. Find agents with spare OCC capacity (< 80% occupancy)
3. Filter by skill match for absent agent's queues
4. Check replacement won't breach 48h/week WTA limit
5. Rank: highest spare capacity first, then seniority
```

**Candidate score:**
```
score = (1 − occupancy_pct/100) × 0.6 + seniority_score × 0.4
```

### Missing Data

- Scheduled roster, skill matrix, absence notifications, seniority data.

---

## Task 11 — Shift Swap Management ⚠️ LIMITED_DATA

**Endpoint:** `GET /api/operations/shift-swap`  
**File:** `operations/routers/task11_shift_swap.py`  
**Reference:** `operations_task_1.pdf §11`

### Validation (when data is available)

```
1. Both agents scheduled on their respective target dates
2. Skill cross-coverage: each agent can do the other's queue
3. Projected weekly hours ≤ 48h per Irish Working Time Act
4. Active agent count on both dates stays above WFM coverage floor
```

### Missing Data

- Scheduled roster, skill matrix, swap request queue, WFM coverage floor.

---

## Task 12 — Schedule Adherence ⚠️ LIMITED_DATA

**Endpoint:** `GET /api/operations/schedule-adherence?query_date=YYYY-MM-DD`  
**File:** `operations/routers/task12_schedule_adherence.py`  
**Reference:** `operations_task_1.pdf §12`, `operations_task_2.pdf §9`

### Formula (requires schedule data)

```
Schedule Adherence % = Adherent Minutes / Scheduled Minutes × 100

Adherent Minutes = minutes agent was in correct status during scheduled window
                   (OCC/CFT when scheduled on-phones; break when scheduled on-break)
```

### Thresholds

| Level | Condition |
|-------|-----------|
| Target | Adherence % >= 90% |
| Supervisor review | Adherence % < 85% |
| Manager escalation | Adherence % < 75% |

### What returns now

Actual login/logout times, OCC/CFT/break minutes per agent — all from CSV.
`adherence_pct = null` with `status = INSUFFICIENT_DATA` until scheduled times are loaded.

### Missing Data

- Scheduled start/end time per agent per day (WFM Schedule Builder)
- Scheduled break windows per agent

---

## Shared Data Layer

**File:** `operations/services/csv_loader.py`

| Function | Returns | Used by |
|----------|---------|---------|
| `get_rows()` | `List[RawRow]` (cached) | All tasks |
| `build_agent_day_aggregates()` | `Dict[(agent_id, date), AgentDayAggregate]` | Tasks 1–6, 8, 12 |
| `build_interval_aggregates()` | `Dict[(date, datetime), IntervalAggregate]` | Tasks 4, 7 |
| `available_dates()` | `List[date]` | All tasks |
| `invalidate_cache()` | None | Cache management |

**`AgentDayAggregate` key fields:**

| Field | Formula |
|-------|---------|
| `production_minutes` | `occ_minutes + cft_minutes` |
| `present_minutes` | `production_minutes + break_minutes + training_minutes` |
| `occupancy_pct` | `occ_minutes / production_minutes × 100` |
| `productivity_pct` | `occ_minutes / present_minutes × 100` |
| `in_office_shrinkage_rate_pct` | `shrinkage_minutes / present_minutes × 100` |

---

## Running the Operations Pillar

**Standalone:**
```bash
uvicorn operations.main:app --reload --port 8001
```

**Swagger UI:** `http://localhost:8001/docs`  
**Health check:** `GET /api/operations/health`

**Mounted into root app (`app/main.py`):**
```python
from operations.main import app as ops_app
app.mount("/operations", ops_app)
```

---

## File Structure

```
operations/
├── main.py                          ← FastAPI app + router registration
├── README.md                        ← This file
├── DATA_REQUIREMENTS.md             ← Missing data specification
├── Agent_Breakdown_140426.csv       ← Source data
├── __init__.py
├── services/
│   ├── __init__.py
│   └── csv_loader.py               ← Shared data layer
└── routers/
    ├── __init__.py
    ├── task1_productive_hours.py
    ├── task2_shrinkage.py
    ├── task3_anomaly_detection.py
    ├── task4_shift_span.py
    ├── task5_occupancy.py
    ├── task6_break_compliance.py
    ├── task7_coverage_monitoring.py
    ├── task8_trend_analysis.py
    ├── task9_leave_grant.py         ← LIMITED_DATA stub
    ├── task10_replacement_decisions.py  ← LIMITED_DATA stub
    ├── task11_shift_swap.py         ← LIMITED_DATA stub
    └── task12_schedule_adherence.py ← LIMITED_DATA (partial data)
```

---

*Source documents: `operations_task_1.pdf`, `operations_task_2.pdf`, `BEST WFM Reference Document v24.0.0`*
