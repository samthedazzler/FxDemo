# Operations API — Demo Inputs Guide

> **Swagger UI:** `http://localhost:8000/docs`  
> **Base URL:** `http://localhost:8000/api/operations`  
> **Start server:** `python run.py`

---

## Quick Reference — Available Dates & Agent IDs

### Dates in CSV (use for Tasks 1–8 and Task 12)

| Date | Day | Notes |
|------|-----|-------|
| `2026-04-12` | Sunday | Weekend shift — shorter hours |
| `2026-04-13` | Monday | Full weekday — most data |
| `2026-04-14` | Tuesday | Full weekday |

### Agent IDs

**Team GE — General Entrypoints (11 agents)**

| Agent ID | Shift | Queue | Notable |
|----------|-------|-------|---------|
| `61581635771227` | MORNING 08:00–16:30 | EMAIL | Approved leave Apr 22 |
| `61581666459416` | DAY 09:00–17:30 | EMAIL_BACKLOG | Pending leave Apr 15 → **GRANT** |
| `61581674139184` | MORNING 08:00–16:30 | CHAT | Chat specialist |
| `61582253126069` | DAY 09:00–17:30 | EMAIL_BACKLOG | Pending leave Apr 16–17 → **GRANT** |
| `61583018368573` | MORNING 08:00–16:30 | EMAIL | Pending leave Apr 28 → **DENY: BLACKOUT** |
| `61585038341143` | DAY 09:00–17:30 | EMAIL_BACKLOG | — |
| `61587856425159` | MORNING 08:00–16:30 | EMAIL | Pending personal day → **GRANT** |
| `61588190284154` | DAY 09:00–17:30 | EMAIL_BACKLOG | — |
| `61588377774860` | MORNING 08:00–16:30 | EMAIL | — |
| `61588388064451` | DAY 09:00–17:30 | EMAIL_BACKLOG | — |
| `61588389996727` | MORNING 08:00–16:30 | EMAIL | — |

**Team ID — Incorrect Disables (9 agents)**

| Agent ID | Shift | Queue | Notable |
|----------|-------|-------|---------|
| `100071773725249` | MORNING 08:00–16:30 | EMAIL | Best replacement candidate (92.8% spare) |
| `61580771977862` | MORNING 08:00–16:30 | EMAIL | **0 annual days left** → DENY: INSUFFICIENT_BALANCE; late arrival Apr 12 |
| `61580818484348` | DAY 09:00–17:30 | EMAIL_BACKLOG | Pending swap with 61581055615480 |
| `61581055615480` | MORNING 08:00–16:30 | EMAIL | — |
| `61581509267603` | MORNING 08:00–16:30 | EMAIL_BACKLOG | **Sick Apr 13** — triggers replacement |
| `61581904917164` | DAY 09:00–17:30 | EMAIL_BACKLOG | **Emergency Apr 14** |
| `61581980363535` | MORNING 08:00–16:30 | EMAIL | — |
| `61588063300667` | DAY 09:00–17:30 | EMAIL_BACKLOG | Pending leave Apr 17 → **GRANT** |
| `61588449381350` | MORNING 08:00–16:30 | EMAIL | — |

---

## Task 1 — Productive Hours

**Endpoint:** `GET /api/operations/productive-hours`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-13` | Monday — most activity |
| `agent_id` | string | *(blank)* | Returns all 20 agents |

**Single agent example:**

| Parameter | Value |
|-----------|-------|
| `query_date` | `2026-04-12` |
| `agent_id` | `61581666459416` |

**cURL:**
```bash
curl "http://localhost:8000/api/operations/productive-hours?query_date=2026-04-13"
curl "http://localhost:8000/api/operations/productive-hours?query_date=2026-04-12&agent_id=61581666459416"
```

**What to look for in response:** `productivity_flag: true` on agents below 85% productivity. `team_avg_productivity_pct` for overall health.

---

## Task 2 — Shrinkage Rate

**Endpoint:** `GET /api/operations/shrinkage-rate`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-13` | — |
| `agent_id` | string | *(blank)* | All agents |

**cURL:**
```bash
curl "http://localhost:8000/api/operations/shrinkage-rate?query_date=2026-04-13"
curl "http://localhost:8000/api/operations/shrinkage-rate?query_date=2026-04-14&agent_id=61581509267603"
```

**What to look for:** `in_office_shrinkage_rate_pct` — agents above 35% are flagged `high_shrinkage: true`. `required_seats_factor` shows how many extra seats WFM needs to plan for.

---

## Task 3 — Anomaly Detection

**Endpoint:** `GET /api/operations/anomaly-detection`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-13` | — |

> No agent filter — anomaly detection requires the full team to compute z-scores.

**All three dates:**
```bash
curl "http://localhost:8000/api/operations/anomaly-detection?query_date=2026-04-12"
curl "http://localhost:8000/api/operations/anomaly-detection?query_date=2026-04-13"
curl "http://localhost:8000/api/operations/anomaly-detection?query_date=2026-04-14"
```

**What to look for:** Agents with `z_score_outlier: true` (z < −2.0). `flags` list — `PRODUCTIVITY_LOW`, `OCCUPANCY_LOW`. `overall_risk` level.

---

## Task 4 — Shift Span & Attendance

**Endpoint:** `GET /api/operations/shift-span`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-12` | Sunday — shorter shifts |
| `agent_id` | string | `61580771977862` | This agent had a **late arrival** on Apr 12 |

**To see all flags:**
```bash
curl "http://localhost:8000/api/operations/shift-span?query_date=2026-04-12"
curl "http://localhost:8000/api/operations/shift-span?query_date=2026-04-13&agent_id=61580771977862"
```

**What to look for:** `attendance_status: LATE_START` or `SHORT_SHIFT`. `flags` array with `reason` and `detail`.

---

## Task 5 — Occupancy Breakdown

**Endpoint:** `GET /api/operations/occupancy`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-13` | Full weekday |
| `agent_id` | string | *(blank)* | All agents |

**cURL:**
```bash
curl "http://localhost:8000/api/operations/occupancy?query_date=2026-04-13"
curl "http://localhost:8000/api/operations/occupancy?query_date=2026-04-14&agent_id=61581674139184"
```

**What to look for:** `occupancy_status: LOW` agents with `routing_flag: true`. `team_avg_occupancy_pct` — current data averages ~64.5% (below healthy 70–85% range).

---

## Task 6 — Break Compliance

**Endpoint:** `GET /api/operations/break-compliance`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-12` | Sunday — shorter shifts, more likely violations |
| `agent_id` | string | *(blank)* | All agents |

**cURL:**
```bash
curl "http://localhost:8000/api/operations/break-compliance?query_date=2026-04-12"
curl "http://localhost:8000/api/operations/break-compliance?query_date=2026-04-13"
```

**What to look for:** `violation_type` — `VIOLATION_6H` (HIGH risk) or `VIOLATION_4H` / `ZERO_BREAK_FULL_SHIFT` (MEDIUM risk). `supervisor_action_required: true`.

---

## Task 7 — Coverage Monitoring

**Endpoint:** `GET /api/operations/coverage-monitoring`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-13` | Full weekday |
| `required_staff` | int | *(blank)* | Returns counts only |
| `required_staff` | int | `15` | Triggers compliance % calculation |
| `required_staff` | int | `20` | Forces many UNDERSTAFFED intervals |

**Without required_staff (counts only):**
```bash
curl "http://localhost:8000/api/operations/coverage-monitoring?query_date=2026-04-13"
```

**With required_staff (compliance %):**
```bash
curl "http://localhost:8000/api/operations/coverage-monitoring?query_date=2026-04-13&required_staff=15"
curl "http://localhost:8000/api/operations/coverage-monitoring?query_date=2026-04-13&required_staff=20"
```

**What to look for:** `interval_compliance_pct` per 30-min slot. `status: UNDERSTAFFED` intervals. `peak_active_agents` vs `min_active_agents`.

---

## Task 8 — Trend Analysis

**Endpoint:** `GET /api/operations/trend-analysis`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `agent_id` | string | *(blank)* | All 20 agents, 3-day trends |
| `agent_id` | string | `61581509267603` | Sick Apr 13 — shows INSUFFICIENT_DATA trend |
| `agent_id` | string | `61581666459416` | Full 3-day trend |

**cURL:**
```bash
curl "http://localhost:8000/api/operations/trend-analysis"
curl "http://localhost:8000/api/operations/trend-analysis?agent_id=61581509267603"
curl "http://localhost:8000/api/operations/trend-analysis?agent_id=61581666459416"
```

**What to look for:** `overall_alert` — `CRITICAL` / `WARNING` / `WATCH` / `OK`. `coaching_priority: true` agents. `occupancy_slope` (negative = declining). `days_present` — agents with 2/3 days show reduced confidence.

---

## Task 9 — Leave Grant Decisions

**Endpoint:** `GET /api/operations/leave-grant`

| Parameter | Type | Notes |
|-----------|------|-------|
| `agent_id` | string | Filter to one agent's requests |
| `request_date` | date | Filter requests starting on/after this date |
| `status_filter` | string | `PENDING` (default) · `ALL` · `APPROVED` · `DENIED` |

### Demo Scenario 1 — All pending requests at once (shows all 4 outcomes)

| Parameter | Value |
|-----------|-------|
| `agent_id` | *(blank)* |
| `status_filter` | `PENDING` |

```bash
curl "http://localhost:8000/api/operations/leave-grant?status_filter=PENDING"
```

**Expected:** 8 requests evaluated — **5 GRANT, 3 DENY**

| Agent | Leave type | Decision | Reason |
|-------|-----------|----------|--------|
| `61581666459416` | ANNUAL | ✅ GRANT | 13 days remaining, team has room, Apr 15 not blacked out |
| `61582253126069` | ANNUAL | ✅ GRANT | 18 days remaining |
| `61580771977862` | ANNUAL | ❌ DENY | **INSUFFICIENT_BALANCE** — 0 days remaining |
| `61581674139184` | ANNUAL | ❌ DENY | **TEAM_AT_CAPACITY** — GE team slot taken Apr 22 |
| `61583018368573` | ANNUAL | ❌ DENY | **BLACKOUT_DATE: PEAK_SEASON** — Apr 28 blocked |
| `61587856425159` | PERSONAL | ✅ GRANT | 2 personal days available |
| `61588063300667` | ANNUAL | ✅ GRANT | 15 days remaining |
| `61581904917164` | SICK | ✅ GRANT | 5 sick days available |

---

### Demo Scenario 2 — GRANT (step-by-step walkthrough)

| Parameter | Value |
|-----------|-------|
| `agent_id` | `61581666459416` |
| `status_filter` | `PENDING` |

```bash
curl "http://localhost:8000/api/operations/leave-grant?agent_id=61581666459416"
```

**Expected response shows all 3 steps PASS:**
```
Step 1 [PASS] — Agent has 13 ANNUAL days remaining
Step 2 [PASS] — 0 agents approved absent on 2026-04-15, limit is 1
Step 3 [PASS] — 2026-04-15 is not a blacked-out date
→ GRANT | balance_before: 13 | balance_after: 12
```

---

### Demo Scenario 3 — DENY: INSUFFICIENT_BALANCE

| Parameter | Value |
|-----------|-------|
| `agent_id` | `61580771977862` |
| `status_filter` | `PENDING` |

```bash
curl "http://localhost:8000/api/operations/leave-grant?agent_id=61580771977862"
```

**Expected:** Step 1 FAIL — only 0 days remaining, 1 requested.

---

### Demo Scenario 4 — DENY: TEAM_AT_CAPACITY

| Parameter | Value |
|-----------|-------|
| `agent_id` | `61581674139184` |
| `status_filter` | `PENDING` |

```bash
curl "http://localhost:8000/api/operations/leave-grant?agent_id=61581674139184"
```

**Expected:** Step 1 PASS (17 days), Step 2 FAIL — team already has 1 approved absence on Apr 22 (agent `61581635771227`), WFM limit is 1.

---

### Demo Scenario 5 — DENY: BLACKOUT_DATE

| Parameter | Value |
|-----------|-------|
| `agent_id` | `61583018368573` |
| `status_filter` | `PENDING` |

```bash
curl "http://localhost:8000/api/operations/leave-grant?agent_id=61583018368573"
```

**Expected:** Step 1 PASS, Step 2 PASS, Step 3 FAIL — Apr 28 falls within PEAK_SEASON blackout (Apr 25–May 5).

---

### Demo Scenario 6 — View already-decided requests

```bash
# Approved (historic)
curl "http://localhost:8000/api/operations/leave-grant?status_filter=APPROVED"

# Denied (historic)
curl "http://localhost:8000/api/operations/leave-grant?status_filter=DENIED"

# Everything
curl "http://localhost:8000/api/operations/leave-grant?status_filter=ALL"
```

---

## Task 10 — Replacement Decisions

**Endpoint:** `GET /api/operations/replacement-decisions`

| Parameter | Type | Notes |
|-----------|------|-------|
| `absent_agent_id` | string | Filter to a specific absent agent |
| `absence_date` | date | Date of absence (YYYY-MM-DD) |

### Demo Scenario 1 — Sick call Apr 13

| Parameter | Value |
|-----------|-------|
| `absent_agent_id` | `61581509267603` |
| `absence_date` | `2026-04-13` |

```bash
curl "http://localhost:8000/api/operations/replacement-decisions?absent_agent_id=61581509267603&absence_date=2026-04-13"
```

**Expected:** Absent agent's queue = `QUEUE_EMAIL_BACKLOG`. Top replacement: `100071773725249` (92.8% spare capacity). All 19 other scheduled agents evaluated, ranked by spare capacity.

---

### Demo Scenario 2 — Emergency absence Apr 14

| Parameter | Value |
|-----------|-------|
| `absent_agent_id` | `61581904917164` |
| `absence_date` | `2026-04-14` |

```bash
curl "http://localhost:8000/api/operations/replacement-decisions?absent_agent_id=61581904917164&absence_date=2026-04-14"
```

---

### Demo Scenario 3 — All absences in dataset

| Parameter | Value |
|-----------|-------|
| `absent_agent_id` | *(blank)* |
| `absence_date` | *(blank)* |

```bash
curl "http://localhost:8000/api/operations/replacement-decisions"
```

**Expected:** All 4 absence notifications returned with ranked candidates for each.

---

## Task 11 — Shift Swap Management

**Endpoint:** `GET /api/operations/shift-swap`

| Parameter | Type | Notes |
|-----------|------|-------|
| `agent_a` | string | Agent giving away their shift |
| `agent_b` | string | Agent taking agent A's shift |
| `agent_a_date` | date | Date agent A wants to give away |
| `agent_b_date` | date | Date agent B wants to give away |
| `status_filter` | string | `PENDING` (default) · `ALL` · `APPROVED` · `DENIED` |

### Demo Scenario 1 — All pending swaps (all APPROVE)

| Parameter | Value |
|-----------|-------|
| *(all blank)* | — |
| `status_filter` | `PENDING` |

```bash
curl "http://localhost:8000/api/operations/shift-swap?status_filter=PENDING"
```

**Expected:** 3 pending requests — **all 3 APPROVE**

| Agent A | Agent A Date | Agent B | Agent B Date | Decision |
|---------|-------------|---------|-------------|----------|
| `61581635771227` | `4/14/2026` | `61581666459416` | `4/13/2026` | ✅ APPROVE |
| `61580818484348` | `4/14/2026` | `61581055615480` | `4/13/2026` | ✅ APPROVE |
| `61580771977862` | `4/13/2026` | `61581674139184` | `4/14/2026` | ✅ APPROVE |

---

### Demo Scenario 2 — Single swap with full check breakdown

| Parameter | Value |
|-----------|-------|
| `agent_a` | `61581635771227` |
| `agent_a_date` | `2026-04-14` |
| `agent_b` | `61581666459416` |
| `agent_b_date` | `2026-04-13` |

```bash
curl "http://localhost:8000/api/operations/shift-swap?agent_a=61581635771227&agent_a_date=2026-04-14&agent_b=61581666459416&agent_b_date=2026-04-13"
```

**Expected 4-check result:**
```
Check 1 [PASS] Both agents scheduled
Check 2 [PASS] Skill cross-coverage — both certified for each other's queue
Check 3 [PASS] Working Time Act 48h/week — pure swap, hours unchanged
Check 4 [PASS] Coverage floor maintained — 19/18 agents remain on each date
→ APPROVE
```

---

### Demo Scenario 3 — View historic denied swap

```bash
curl "http://localhost:8000/api/operations/shift-swap?status_filter=ALL"
```

**Expected:** Shows 3 APPROVE + 1 historic APPROVED + 1 historic DENIED (COVERAGE_FLOOR_BREACH on weekend Apr 12).

---

## Task 12 — Schedule Adherence

**Endpoint:** `GET /api/operations/schedule-adherence`

| Parameter | Type | Demo Value | Notes |
|-----------|------|------------|-------|
| `query_date` | date ✅ | `2026-04-13` | Monday — most data |
| `agent_id` | string | *(blank)* | All agents |

### Demo Scenario 1 — Team adherence Monday

| Parameter | Value |
|-----------|-------|
| `query_date` | `2026-04-13` |
| `agent_id` | *(blank)* |

```bash
curl "http://localhost:8000/api/operations/schedule-adherence?query_date=2026-04-13"
```

**Expected:** 14 agents — avg ~39% adherence. All show `MANAGER_ESCALATION` because the CSV captures a ~3–4 hour activity window while the scheduled shift is 8.5 hours. `early_departure_minutes` shows the gap (150–260 min for most agents).

---

### Demo Scenario 2 — Sick agent (lowest adherence)

| Parameter | Value |
|-----------|-------|
| `query_date` | `2026-04-13` |
| `agent_id` | `61581509267603` |

```bash
curl "http://localhost:8000/api/operations/schedule-adherence?query_date=2026-04-13&agent_id=61581509267603"
```

**Expected:** ~42% adherence — sick agent logged in briefly then went absent.

---

### Demo Scenario 3 — All three dates

```bash
curl "http://localhost:8000/api/operations/schedule-adherence?query_date=2026-04-12"
curl "http://localhost:8000/api/operations/schedule-adherence?query_date=2026-04-13"
curl "http://localhost:8000/api/operations/schedule-adherence?query_date=2026-04-14"
```

---

## Recommended 5-Call Demo Path

Run these in order for a complete end-to-end walkthrough:

```bash
# 1. Live occupancy heatmap — see which agents are LOW/HEALTHY/HIGH
curl "http://localhost:8000/api/operations/occupancy?query_date=2026-04-13"

# 2. Break compliance — legal violations flagged
curl "http://localhost:8000/api/operations/break-compliance?query_date=2026-04-12"

# 3. 3-day trend — who is declining and needs coaching
curl "http://localhost:8000/api/operations/trend-analysis"

# 4. Leave grant — all 4 decision outcomes in one call
curl "http://localhost:8000/api/operations/leave-grant?status_filter=PENDING"

# 5. Shift swap — 4-check validation
curl "http://localhost:8000/api/operations/shift-swap?status_filter=PENDING"
```

---

## Data Files Reference

All demo data lives in `operations/data/`:

| File | Used by | Key content |
|------|---------|-------------|
| `Agent_Breakdown_140426.csv` | Tasks 1–8, 12 | 2113 rows, 3 days, 20 agents |
| `leave_entitlements.csv` | Task 9 | 60 rows — annual/sick/personal balances |
| `leave_requests.csv` | Task 9 | 11 requests — 8 PENDING, 2 APPROVED, 1 DENIED |
| `wfm_leave_allowance.csv` | Task 9 | Max 1 concurrent absent per team per date |
| `blackout_calendar.csv` | Task 9 | 3 blackout periods — peak season + bank holiday |
| `scheduled_roster.csv` | Tasks 10–12 | 60 rows — all agents × 3 days, start/end/break |
| `skill_matrix.csv` | Tasks 10–11 | 64 rows — queue certifications per agent |
| `shift_swap_requests.csv` | Task 11 | 5 requests — 3 PENDING, 1 APPROVED, 1 DENIED |
| `absence_notifications.csv` | Task 10 | 4 absences — sick, emergency, late arrival |
| `overtime_consent.csv` | Task 10 | 7 agents on standby consent |

---

*Generated for Teleperformance-Dublin — Apr 12–14 2026 dataset.*
