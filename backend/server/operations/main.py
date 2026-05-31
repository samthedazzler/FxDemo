"""
Operations Pillar — FastAPI application entry point
=====================================================
Reference: operations_task_1.pdf, operations_task_2.pdf

This module registers all 12 Operations task routers under /api/operations.
It can be run standalone (uvicorn operations.main:app) or mounted into the
root app (app/main.py) as a sub-application.

Tasks 1–8: Fully operational — all data sourced from Agent_Breakdown_140426.csv.
Tasks 9–12: Stub endpoints (LIMITED_DATA) — require schedule/roster/HR integration.

All endpoints: GET /api/operations/<task-path>
Swagger UI (standalone): /docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from operations.routers import (
    productive_hours,
    shrinkage,
    anomaly_detection,
    shift_span,
    occupancy,
    break_compliance,
    coverage_monitoring,
    trend_analysis,
    leave_grant,
    replacement_decisions,
    shift_swap,
    schedule_adherence,
)

app = FastAPI(
    title="Operations Pillar — WFM SaaS",
    version="1.0.0",
    description=(
        "Decision-making layer over WFM + Finance data. "
        "12 task endpoints covering productive hours, shrinkage, anomaly detection, "
        "shift span, occupancy, break compliance, coverage monitoring, trend analysis, "
        "and stub endpoints for leave, replacement, shift swap, and schedule adherence. "
        "Source documents: operations_task_1.pdf, operations_task_2.pdf, BEST WFM v24.0.0."
    ),
    openapi_tags=[
        {
            "name": "Operations — Live Data",
            "description": "Tasks 1–8: fully operational from Agent_Breakdown_140426.csv.",
        },
        {
            "name": "Operations — Limited Data",
            "description": (
                "Tasks 9–12: stub endpoints. Cannot produce decisions without "
                "scheduled roster, skill matrix, leave entitlement, and WFM allowance schedule. "
                "See /api/operations/data-requirements for full spec."
            ),
        },
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_OPS_PREFIX = "/api/operations"
_LIVE_TAG = "Operations — Live Data"
_LIMITED_TAG = "Operations — Limited Data"

# ── Tasks 1–8: live data from CSV ──────────────────────────────────────────
app.include_router(productive_hours.router,    prefix=_OPS_PREFIX, tags=[_LIVE_TAG])
app.include_router(shrinkage.router,           prefix=_OPS_PREFIX, tags=[_LIVE_TAG])
app.include_router(anomaly_detection.router,   prefix=_OPS_PREFIX, tags=[_LIVE_TAG])
app.include_router(shift_span.router,          prefix=_OPS_PREFIX, tags=[_LIVE_TAG])
app.include_router(occupancy.router,           prefix=_OPS_PREFIX, tags=[_LIVE_TAG])
app.include_router(break_compliance.router,    prefix=_OPS_PREFIX, tags=[_LIVE_TAG])
app.include_router(coverage_monitoring.router, prefix=_OPS_PREFIX, tags=[_LIVE_TAG])
app.include_router(trend_analysis.router,      prefix=_OPS_PREFIX, tags=[_LIVE_TAG])

# ── Tasks 9–12: limited data stubs ─────────────────────────────────────────
app.include_router(leave_grant.router,          prefix=_OPS_PREFIX, tags=[_LIMITED_TAG])
app.include_router(replacement_decisions.router, prefix=_OPS_PREFIX, tags=[_LIMITED_TAG])
app.include_router(shift_swap.router,           prefix=_OPS_PREFIX, tags=[_LIMITED_TAG])
app.include_router(schedule_adherence.router,   prefix=_OPS_PREFIX, tags=[_LIMITED_TAG])


@app.get("/api/operations/health", tags=[_LIVE_TAG])
def ops_health():
    return {
        "status": "ok",
        "pillar": "operations",
        "tasks_live": list(range(1, 9)),
        "tasks_limited_data": list(range(9, 13)),
    }
