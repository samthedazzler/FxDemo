# Project Checklist & Implementation Roadmap

This document keeps track of all planned tasks, in-progress items, and completed actions for the Workforce Management (WFM) System & Finance Integration.

---

## 📅 Roadmap Overview

- [x] **Phase 0: Foundations & Analysis** (Document parsing, system audits, environment setup)
- [ ] **Phase 1: Backend Optimization & Route Review** (Resolving deprecation warnings, database concurrency, local server stability)
- [ ] **Phase 2: Frontend Module Recreation** (Building JavaFX scenes, layouts, and HSL CSS designs)
- [ ] **Phase 3: Integration, SSE Streaming, & Verification** (Wire connection, end-to-end dry runs, and final audit certification)

---

## 🛠️ Detailed Task Checklist

### Phase 0: Foundations & Analysis
- [x] Read and analyze WFM Wireframe PDF (`WFM_Pillar_Wireframe_Specification_v2.0.pdf`)
- [x] Read and analyze Finance Implementation PDF (`WFM_Finance_Implementation_Report.pdf`)
- [x] Remove the deprecated frontend specification PDF (`Complete Wfm Javafx Frontend Specification Document.pdf`)
- [x] Inspect existing FastAPI routes and map out all endpoints
- [x] Audit backend server by running unit tests via `pytest`
- [x] Create project memory files inside `FxDemo/` root:
  - [x] `SECOND_BRAIN.md`
  - [x] `ARCHITECTURE.md`
  - [x] `TODO.md`

### Phase 1: Backend Optimization & Route Review
- [ ] Review and patch deprecated `datetime.utcnow()` occurrences in:
  - [ ] `leave_service.py`
  - [ ] `rate_card_service.py`
  - [ ] `models/db.py`
- [ ] Evaluate SQLite concurrency locks:
  - [ ] Adjust SQLAlchemy engine connection settings (`timeout=30.0`)
  - [ ] Consider enabling WAL (Write-Ahead Logging) mode on start
- [ ] Stabilize embedded server path resolution in `FastApiServer.java` (switch from raw `Path.of("")` to directory-relative path)
- [ ] Double-check database Numeric field mappings for float precision safety

### Phase 2: Frontend Module Recreation
- [ ] Recreate primary layout in `hello-view.fxml` with a collapsible sidebar for the **Hourly Breakdown Model**
- [ ] Implement premium UI views for the 8 sub-modules:
  - [ ] **Module 1: Dashboard View** (Live H Indicators, 6-Month Coverage line chart, feed updates)
  - [ ] **Module 2: Forecast Studio View** (Assumptions grid, learning curve weightings, impact registry)
  - [ ] **Module 3: Capacity Planner View** (Req/Capacity build engine, stakeholder sign-off workflow)
  - [ ] **Module 4: Schedule Builder View** (Interval grids, 85%-115% compliance readout)
  - [ ] **Module 5: RTM Console View** (Live SL ticker, infraction monitor list, Action matrix)
  - [ ] **Module 6: Routing Manager View** (Queue-skill matrix priority mapping)
  - [ ] **Module 7: Leave Planner View** (Slot calendar, wave booking configuration)
  - [ ] **Module 8: GM Estimator View** (Hourly breakdown stage comparison table, What-If simulator)
  - [ ] **Erlang Suite Views** (Staffing calculators for Erlang C & Erlang B)
- [ ] Create HSL-based Dark Mode styling in `views/dashboard.css` with smooth transitions

### Phase 3: Integration & SSE Ingest Streaming
- [ ] Establish `FastApiClient` connection with JSON serialization matching backend models
- [ ] Wire up real-time SSE stream reader in JavaFX for multipart CSV upload progress (`/ingest/csv/stream`)
- [ ] Write integration test cases for checking live frontend-backend connectivity
- [ ] Run full end-to-end dry run (CSV ingest -> billing engine -> monthly rollup -> audit log check)
- [ ] Obtain final system stakeholder verification sign-off
