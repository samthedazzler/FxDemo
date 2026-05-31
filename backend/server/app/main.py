"""WFM x Finance Integration — FastAPI entry point.

Implements the design document `WFM_Finance_Integration_Design.pdf` v0.1.

Architecture summary (section 3.1):
  - WFM Aggregator        -> /finance/breakdown/from-wfm-raw (services/wfm_aggregator.py)
  - Leave Ledger          -> /leaves (services/leave_service.py)
  - Rate Card Service     -> /rate-card  (services/rate_card_service.py)
  - Billing Engine        -> services/billing_engine.py (the pure 7-step pipeline)
  - Reconciliation Service-> /reconciliation (services/reconciliation_service.py)

Java frontend compatibility:
  - CORS enabled for typical Java/JVM dev ports (Spring Boot 8080, Vaadin 8081, etc.)
  - All responses are plain JSON with snake_case fields matching the design doc
  - OpenAPI spec auto-published at /openapi.json and Swagger UI at /docs
    -> Java clients can be generated with `openapi-generator-cli generate -i openapi.json
       -g java -o ./generated-client`
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routers import (
    agents,
    leaves,
    rate_card,
    reconciliation,
    status_mapping,
    audit,
    holidays,
    ingest,
)
from finance_func.app.routers import finance
from wfm.routers import (
    dashboard as wfm_dashboard,
    forecast as wfm_forecast,
    capacity as wfm_capacity,
    schedule as wfm_schedule,
    rtm as wfm_rtm,
    erlang as wfm_erlang,
    gm_estimator as wfm_gm,
)
from operations.routers import (
    productive_hours as ops_productive_hours,
    shrinkage as ops_shrinkage,
    anomaly_detection as ops_anomaly_detection,
    shift_span as ops_shift_span,
    occupancy as ops_occupancy,
    break_compliance as ops_break_compliance,
    coverage_monitoring as ops_coverage_monitoring,
    trend_analysis as ops_trend_analysis,
    leave_grant as ops_leave_grant,
    replacement_decisions as ops_replacement_decisions,
    shift_swap as ops_shift_swap,
    schedule_adherence as ops_schedule_adherence,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Agent-Level Financial Model — implements the WFM x Finance Integration "
        "design v0.1. Five components (WFM Aggregator, Leave Ledger, Rate Card, "
        "Billing Engine, Reconciliation) and the deterministic seven-step pipeline."
    ),
    contact={"name": "Finance Platform", "email": "finance-platform@example.com"},
    openapi_tags=[
        {"name": "Finance", "description": "Section 7 — WFM <-> Finance contract."},
        {"name": "Agent Master (HR)", "description": "Section 4.1 — agent contract data."},
        {"name": "Leave Ledger (HR)", "description": "Section 4.2 — leave balances."},
        {"name": "Rate Card Service", "description": "Section 3.1 + 10 — versioned rates."},
        {"name": "Reconciliation", "description": "Section 6.4 — nightly checks + pending queue."},
        {"name": "Status Mapping (Appendix)", "description": "Section 11 — Status -> Pay Category."},
        {"name": "Audit", "description": "Section 8 — auditability & compliance log."},
        {"name": "Holiday Calendar", "description": "Section 10 — per-site holiday calendar."},
        {"name": "CSV Ingest", "description": "Streaming ingest from Agent_Breakdown_*.csv."},
        {"name": "Dashboard", "description": "WFM live operations dashboard KPIs."},
        {"name": "Forecast Studio", "description": "WFM volume / AHT / shrinkage forecast assumptions."},
        {"name": "Capacity Planner", "description": "WFM requirement & capacity FTE build."},
        {"name": "Schedule Builder", "description": "WFM interval-level schedule coverage."},
        {"name": "RTM Console", "description": "Real-time management adherence + action log."},
        {"name": "Erlang Calculator", "description": "Erlang B / C staffing calculations."},
        {"name": "GM Estimator", "description": "Gross-margin scenario / what-if estimator."},
        {"name": "Operations — Live Data", "description": "Tasks 1–8: productive hours, shrinkage, anomaly detection, shift span, occupancy, break compliance, coverage monitoring, trend analysis."},
        {"name": "Operations — Limited Data", "description": "Tasks 9–12: leave grant, replacement decisions, shift swap, schedule adherence — stubs pending WFM/HR data integration."},
    ],
)

# Java frontend compatibility — permissive CORS for typical JVM dev ports.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "VALIDATION_FAILED", "details": exc.errors()},
    )


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


app.include_router(agents.router)
app.include_router(leaves.router)
app.include_router(rate_card.router)
app.include_router(holidays.router)
app.include_router(finance.router)
app.include_router(reconciliation.router)
app.include_router(status_mapping.router)
app.include_router(audit.router)
app.include_router(ingest.router)

# Original WFM platform routers (capacity / forecast / schedule / rtm / erlang / gm).
app.include_router(wfm_dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(wfm_forecast.router,  prefix="/api/forecast",  tags=["Forecast Studio"])
app.include_router(wfm_capacity.router,  prefix="/api/capacity",  tags=["Capacity Planner"])
app.include_router(wfm_schedule.router,  prefix="/api/schedule",  tags=["Schedule Builder"])
app.include_router(wfm_rtm.router,       prefix="/api/rtm",       tags=["RTM Console"])
app.include_router(wfm_erlang.router,    prefix="/api/erlang",    tags=["Erlang Calculator"])
app.include_router(wfm_gm.router,        prefix="/api/gm",        tags=["GM Estimator"])

# Operations pillar routers — Tasks 1–8 (live CSV data) and Tasks 9–12 (limited data stubs)
_OPS = "/api/operations"
_OPS_LIVE    = "Operations — Live Data"
_OPS_LIMITED = "Operations — Limited Data"
app.include_router(ops_productive_hours.router,    prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_shrinkage.router,           prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_anomaly_detection.router,   prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_shift_span.router,          prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_occupancy.router,           prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_break_compliance.router,    prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_coverage_monitoring.router, prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_trend_analysis.router,      prefix=_OPS, tags=[_OPS_LIVE])
app.include_router(ops_leave_grant.router,          prefix=_OPS, tags=[_OPS_LIMITED])
app.include_router(ops_replacement_decisions.router, prefix=_OPS, tags=[_OPS_LIMITED])
app.include_router(ops_shift_swap.router,           prefix=_OPS, tags=[_OPS_LIMITED])
app.include_router(ops_schedule_adherence.router,   prefix=_OPS, tags=[_OPS_LIMITED])

# Static frontend (the original WFM index.html lives at repo-root /static/).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATIC_DIR = os.path.join(_REPO_ROOT, "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def serve_frontend():
    index_path = os.path.join(_STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return JSONResponse(
            {"error": "index.html not found", "static_dir": _STATIC_DIR},
            status_code=404,
        )
    return FileResponse(index_path)
