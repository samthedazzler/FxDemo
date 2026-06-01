# Second Brain — Workforce Management (WFM) Module Memory

This document is the persistent memory and developer reference for the Workforce Management (WFM) module of the AI Enterprise Operations Intelligence Platform. It synthesizes the structural, mathematical, and functional requirements from the specification sheets.

---

## 1. Core Computational Spine: The Hourly Breakdown Model

Every module computes against this linear model per **BEST WFM §2.2**. It forms the mathematical backbone connecting forecasting to capacity planning and gross margin.

```
OFFERED VOLUME
  │
  ├── Abandoned Transactions
  │
  └── HANDLED VOLUME (= Offered − Abandoned)
          │
          × AHT ÷ Concurrency Rate
          │
          └── TRANSACTION HOURS
                  │
                  + Available Hours
                  │
                  └── PRODUCTION HOURS
                          │
                          + In-Office Shrinkage Hours
                          │
                          └── PRESENT HOURS (excl. NHT)
                                  │
                                  + Unplanned Out-Office Shrinkage Hours
                                  │
                                  └── SCHEDULED HOURS NET
                                          │
                                          + Planned Out-Office Shrinkage Hours
                                          │
                                          └── SCHEDULED HOURS GROSS
```

### 1.1 Formula Glossary

| Metric / Rate | Formula | Description |
| :--- | :--- | :--- |
| **Abandon Rate** | $\text{Abandoned} \div \text{Offered Volume}$ | Proportion of calls abandoned before connecting. |
| **Availability Rate** | $\text{Available Hours} \div \text{Production Hours}$ | Idle time during production. |
| **Occupancy** | $\text{Transaction Hours} \div \text{Production Hours}$ | Proportion of productive time spent actively handling. |
| **In-Office Shrinkage** | $\text{In-Office Shrinkage Hours} \div \text{Present Hours}$ | breaks, meetings, internal training. |
| **Unplanned Out-Office Shrinkage** | $\text{Unplanned Out-Office Hours} \div \text{Scheduled Hours Net}$ | Sickness, unplanned absences, no-shows. |
| **Planned Out-Office Shrinkage** | $\text{Planned Out-Office Hours} \div \text{Scheduled Hours Gross}$ | Pre-approved vacations, planned leaves. |
| **Efficiency** | $\text{Transaction Hours} \div \text{Present Hours (excl. NHT)}$ | Total transaction throughput vs present time. |
| **Utilisation** | $\text{Production Hours} \div \text{Present Hours (excl. NHT)}$ | Time available for transactions vs present time. |

---

## 2. Workforce Management Sub-Modules

### Module 1: WFM Dashboard
Single-pane-of-glass overview showing key health indicators (target benchmarks):
- **Requirement Coverage Rate**: target 100% ($\text{Capacity Production Hrs} \div \text{Requirement Production Hrs}$)
- **Scheduling Efficiency**: target $\ge 75\%$ (% of intervals within $\pm X\%$ of requirement)
- **Adherence Rate**: target $\ge 95\%$ ($\text{Actual Present Hours} \div \text{Scheduled Hours}$)
- **Forecast Accuracy (FCA)**: target $\ge 85\%$ ($\text{Actuals} \div \text{Forecasted Volume}$)
- **Occupancy**: target $< 85\%$
- **Gross Margin Estimate**: tracked against budget (e.g., target 35%)

### Module 2: Forecast Studio
Exposes five forecast types:
1. **Long-Term**: 4+ months horizon (Indicative, non-binding).
2. **Guidance**: 2-3 months horizon (Indicative, non-binding).
3. **Locked**: +1 month horizon (Contractually binding).
4. **Internally Agreed**: +1 month horizon (WFM planning basis, binding).
5. **Advisory**: Current month (Trend monitoring, informative).

*Key Features:*
- **AHT Learning Curve Manager**: Weighted AHT based on Customer Expert (CE) seniority cohorts (e.g., Tenured W5 AHT=626s, Senior W12+ AHT=450s, Nesting/New Hire W1 AHT=1200s).
- **Event Impact Register**: Quantifies and stores historical impacts (e.g., Payment Cycle Peak +18%, Summer Bank Holiday -35%, Black Friday +45%).

### Module 3: Capacity Planner
Builds 6-month rolling capacity FTE plan at weekly granularity.
- **Requirement Build Engine**: Uses the Hourly Breakdown Model to translate Offered Volume to FTE Requirement (Gross).
- **Capacity Build Engine**: Accumulates starting FTEs, subtracts Leavers, adds New Hires/Transfers to verify Requirement Coverage Rate.
- **Recruitment & Training Tracker**: Details NHT (New Hire Training) batches, nesting duration, trainer assignment, and class capacities.

### Module 4: Schedule Builder
Interval-level optimization at 15–30 min granularity.
- **Interval Coverage Grid**: Displays Required, Scheduled, and Actual headcount (HC) along with GAP and action recommendations (e.g., Move to OT, Offer VTO).
- **Enforces Compliance**:
  - Scheduling Efficiency: Target $\ge 75\%$ of intervals within 85%–115% threshold.
  - Conformance to legal and shift constraints (e.g., maximum shift span, rest intervals).
  - New Hire pairing with supervisors during nesting.

### Module 5: RTM Console
Proactive, real-time command center refreshing every 30s.
- **Real-Time KPI Dashboard**: Service Level, AHT, Queue Depth, Average Speed of Answer (ASA), Abandon Rate.
- **Adherence Monitor**: Live agent states compared against schedules (On Call, ACW, Break, Training, Absent) with automated infraction alerts (e.g., Extended Break, Long ACW).
- **RTM Action Matrix**:
  - **White (Over-delivery, SL >85%)**: Initiate VTO, move agents to coaching/meetings.
  - **Green (On-target, SL 80%-85%)**: Monitor closely, block extra shrinkage.
  - **Amber (Under-delivery, SL 75%-80%)**: Prioritize low SL queues, multi-skill routing.
  - **Red (Critical, SL <75%)**: Cancel non-essential shrinkage, shift breaks, collect OT.

### Module 6: Routing Manager
Organizes Queue $\times$ Skill Matrix.
- **Routing Priority**: Assigns Primary (P1) and Backup (P2) skill combinations.
- **Availability Optimization**: Simulates multi-skilling benefits (e.g., target Availability Rate $\le 32\%$; reduces idle time compared to single-skill silos).

### Module 7: Leave Planner
Vacation slot planner.
- **Available Slot Calculator**: Converts capacity buffer above 100% coverage to available leave slots per day/LOB.
- **Rotational Prioritisation Waves**:
  - Wave 1: Single parents & carers (opens June 1).
  - Wave 2: Seniority >2 years (opens June 8).
  - Wave 3: Low absenteeism <3% (opens June 15).
  - Wave 4: Rest of team (opens June 22).

### Module 8: GM Estimator
Calculates Gross Margin across all planning stages:
$$\text{Gross Margin} = \frac{\text{Revenue} - \text{Direct Costs}}{\text{Revenue}}$$
- **Revenue Drivers**: Tracks billing models (Per Transaction, Per Transaction Hour, Per Production Hour, Per Present Hour, Per Employed FTE).
- **Direct Cost Drivers**: Salaries, bonuses, recruitment costs, benefit provisioning.
- **What-If Scenario Simulator**: Projects margin impact of changing variables (e.g., AHT -30s improves margin by +0.8pp).

---

## 3. Database Schema Context (SQLite)

The backend local SQLite database is named `wfm_finance.db`. Its schemas map out core entities:

```
┌──────────────┐      ┌─────────────────┐      ┌────────────────────┐
│    Agent     │ ───< │   LeaveLedger   │ ───< │ FinancialBreakdown │
└──────────────┘      └─────────────────┘      └────────────────────┘
       │                                                 │
       │                                                 ▼
       │      ┌─────────────────┐              ┌────────────────────┐
       └────< │ HourlyBreakdown │              │      AuditLog      │
              └─────────────────┘              └────────────────────┘
```

### 3.1 Primary Schema Tables

- **`agents` (Agent Master)**:
  - `agent_id` (PK): Text, unique identifier.
  - `name`: Text, agent name.
  - `primary_site`: Text (drives regional holidays).
  - `min_monthly_pay`: Float/Numeric.
  - `max_monthly_pay`: Float/Numeric (Nullable).
  - `regular_hourly_rate`: Float/Numeric.
  - `ot_multiplier`: Float/Numeric (default 1.5).
  - `holiday_multiplier`: Float/Numeric (default 2.0).
  - `night_premium_rate`: Float/Numeric (default 0.10).

- **`leave_ledgers` (Leave Ledger)**:
  - `id` (PK): Integer.
  - `agent_id` (FK): Text.
  - `leave_type`: Text (ANNUAL, PUBLIC_HOLIDAY, SICKNESS, LWP, PENDING_APPROVAL).
  - `accrued_days`: Float.
  - `used_days`: Float.
  - `pending_days`: Float.
  - `policy`: Text (BLOCK, UNPAID_AUTO, MANAGER_APPROVAL).

- **`hourly_breakdowns` (WFM Hourly Inputs)**:
  - `agent_id` (FK), `date` (Composite PK).
  - `productive_minutes`, `available_minutes`, `break_minutes`, `training_minutes`, `scheduled_minutes`, `worked_minutes`, `overtime_minutes`, `night_minutes`: Float.
  - `is_holiday`: Boolean.
  - `site`: Text.
  - `source_status_breakdown`: JSON/Text (Appendix status routing).

- **`financial_breakdowns` (Per-Agent Daily Financials)**:
  - `id` (PK): Integer.
  - `agent_id` (FK): Text.
  - `date`: Date.
  - `regular_pay`, `overtime_pay`, `holiday_pay`, `night_premium`, `leave_pay`: Numeric.
  - `daily_gross`, `month_to_date_gross`, `projected_monthly_gross`, `monthly_pay`: Numeric.
  - `delta_reason`, `min_max_status`: Text.
  - `billing_status`: Text (PAID, UNPAID_LWP, PENDING_APPROVAL, BLOCKED).
  - `content_hash`: Text (provenance SHA-256).
  - `parent_id`: Integer (FK to self for correction history).
  - `rate_card_version`: Text.
  - `provenance`: JSON/Text.

- **`audit_logs` (Compliance Ledger)**:
  - `id` (PK): Integer.
  - `event_type`: Text (BILLING_COMPUTED, BILLING_BLOCKED, MANAGER_DECISION, LEAVE_BALANCE_ADJUSTED).
  - `actor`: Text.
  - `timestamp`: DateTime.
  - `payload`: JSON/Text.
  - `content_hash`: Text.

---

## 4. FastAPI Routes Registry (33 Endpoints)

The FastAPI server listens on port `8000`. It registers routes across the following groups:

### 4.1 Finance (WFM <-> Finance Contract)
- `POST /finance/breakdown`: Process daily shift end event; returns cost breakdown.
- `POST /finance/breakdown/from-wfm-raw`: Accepts raw status mapping; aggregates and processes.
- `POST /finance/preview`: Synchronous OT request cost preview and approval recommendation.
- `GET /finance/breakdown/{agent_id}/{work_date}`: Read specific daily financial record.
- `GET /finance/breakdown/{agent_id}`: Read financial range records for an agent.
- `GET /finance/monthly/{agent_id}/{year}/{month}`: Monthly rollup with min/max check applied.

### 4.2 Agent Master (HR)
- `GET /agents`: List all CEs in the Master list.
- `POST /agents`: Create/enroll a new CE.
- `GET /agents/{agent_id}`: Retrieve agent parameters (base rate, min/max pay floors).
- `PUT /agents/{agent_id}`: Update agent contract details.
- `DELETE /agents/{agent_id}`: Remove agent.

### 4.3 Leave Ledger (HR)
- `GET /leaves`: Retrieve all leave balances.
- `POST /leaves/adjust`: Adjust leave balances or enforce manual HR overrides.

### 4.4 Rate Cards
- `GET /rate-card`: Retrieve versioned rate structures.
- `POST /rate-card`: Create or update a rate card.

### 4.5 Holidays
- `GET /holidays`: List regional calendars.
- `POST /holidays`: Add site holiday date.

### 4.6 Reconciliation
- `GET /reconciliation/run`: Perform daily integrity variance checks.
- `GET /reconciliation/pending-approvals`: View all pending MANAGER_APPROVAL items.
- `POST /reconciliation/pending-approvals/{id}/decision`: Record manager's APPROVE or DENY.

### 4.7 CSV Ingest
- `POST /ingest/csv/path`: Trigger server-side CSV streaming ingest.
- `POST /ingest/csv/upload`: Multipart upload endpoint.
- `GET /ingest/csv/stream`: Server-Sent Events (SSE) live progress feed.
- `GET /ingest/csv/preview`: Fetch limited preview rows.

### 4.8 WFM Module Endpoints (`/api/dashboard`, `/api/forecast`, etc.)
- Dashboard, Forecast, Capacity, Schedule, RTM, Erlang, and GM stubs.

---

## 5. Discovered Server Issues & Notes

1. **`datetime.utcnow()` Deprecation Warnings**: Emitted in Python 3.12+ / 3.14. Found in `leave_service.py:183`, `rate_card_service.py:57, 92`, and `models/db.py`.
2. **SQLite Database Locking**: Large bulk uploads can lead to database connection timeouts.
3. **Relative File Resolutions**: ProcessBuilder in `FastApiServer.java` depends on project-root directory context for locating `python.exe`.
