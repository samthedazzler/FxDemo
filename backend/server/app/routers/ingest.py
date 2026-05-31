"""Streaming CSV ingest endpoints.

The Java frontend can drive ingest in three ways:

  1. `POST /ingest/csv/path`   -- server reads a CSV file by path (the one
                                 configured in `settings.wfm_csv_path` by
                                 default).
  2. `POST /ingest/csv/upload` -- multipart upload from the browser.
  3. `GET  /ingest/csv/stream` -- Server-Sent Events feed of per-agent-day
                                 results, ideal for a live progress UI.

All three drive the same `csv_pipeline.stream_ingest` generator, so the
section 5.1 seven-step pipeline runs unchanged for every record.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.services import csv_pipeline

router = APIRouter(prefix="/ingest", tags=["CSV Ingest"])


class IngestSummary(BaseModel):
    source: str
    total_rollups: int
    ok: int
    blocked: int
    skipped_unknown_agents: int
    errors: int
    results: list[dict]


def _summarise(results: list[csv_pipeline.IngestResult], source: str) -> IngestSummary:
    ok = sum(1 for r in results if r.status == "OK")
    blocked = sum(1 for r in results if r.status == "BLOCKED")
    skipped = sum(1 for r in results if r.status == "SKIPPED_UNKNOWN_AGENT")
    errors = sum(1 for r in results if r.status == "ERROR")
    return IngestSummary(
        source=source,
        total_rollups=len(results),
        ok=ok,
        blocked=blocked,
        skipped_unknown_agents=skipped,
        errors=errors,
        results=[r.to_dict() for r in results],
    )


@router.post("/csv/path", response_model=IngestSummary)
def ingest_from_path(
    path: Optional[str] = Query(None, description="CSV path on the server filesystem."),
    only_agent_id: Optional[str] = Query(None, description="Restrict ingest to a single agent."),
    auto_create_unknown_agents: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Server reads `Agent_Breakdown_140426.csv` (or the supplied path) and
    runs the full streaming ingest. Returns a summary + per-agent-day
    results."""
    csv_path = Path(path) if path else Path(settings.wfm_csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found at {csv_path}")
    results = list(
        csv_pipeline.stream_ingest(
            db, csv_path, only_agent_id=only_agent_id,
            auto_create_unknown_agents=auto_create_unknown_agents,
        )
    )
    return _summarise(results, str(csv_path))


@router.post("/csv/upload", response_model=IngestSummary)
def ingest_from_upload(
    file: UploadFile = File(...),
    only_agent_id: Optional[str] = Query(None),
    auto_create_unknown_agents: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Accept a multipart CSV upload from the Java frontend."""
    import io

    raw = file.file.read()
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig")
    else:
        text = raw
    buf = io.StringIO(text)
    results = list(
        csv_pipeline.stream_ingest(
            db, buf, only_agent_id=only_agent_id,
            auto_create_unknown_agents=auto_create_unknown_agents,
        )
    )
    return _summarise(results, file.filename or "upload.csv")


@router.get("/csv/stream")
def stream_csv_progress(
    path: Optional[str] = Query(None),
    only_agent_id: Optional[str] = Query(None),
    auto_create_unknown_agents: bool = Query(False),
):
    """Server-Sent Events feed.

    Each event is a JSON object representing one agent-day result. The
    stream is naturally bounded by the size of the input CSV; the Java
    frontend subscribes with `new EventSource('/ingest/csv/stream')` and
    renders updates as they arrive.

    Holds its own DB session (one transaction per record) so the response
    can stream without blocking the request session pool.
    """
    csv_path = Path(path) if path else Path(settings.wfm_csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found at {csv_path}")

    def _event_stream():
        db = SessionLocal()
        try:
            counter = 0
            for result in csv_pipeline.stream_ingest(
                db,
                csv_path,
                only_agent_id=only_agent_id,
                auto_create_unknown_agents=auto_create_unknown_agents,
            ):
                counter += 1
                payload = result.to_dict()
                payload["seq"] = counter
                yield f"event: rollup\ndata: {json.dumps(payload)}\n\n"
            yield f"event: done\ndata: {json.dumps({'total_rollups': counter})}\n\n"
        finally:
            db.close()

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering for SSE
        },
    )


@router.get("/csv/preview")
def preview_aggregation(
    path: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=200),
    only_agent_id: Optional[str] = Query(None),
):
    """Dry-run: return the first `limit` daily rollups WITHOUT running the
    Billing Engine. Useful for the Java frontend's 'preview file before
    ingest' UX."""
    from app.services import csv_ingest

    csv_path = Path(path) if path else Path(settings.wfm_csv_path)
    if not csv_path.exists():
        raise HTTPException(status_code=404, detail=f"CSV not found at {csv_path}")

    out: list[dict] = []
    for rollup in csv_ingest.stream_rollups(csv_path, only_agent_id=only_agent_id):
        out.append(
            {
                "agent_id": rollup.agent_id,
                "work_date": rollup.work_date.isoformat(),
                "site": rollup.site,
                "status_minutes": {k: str(v) for k, v in rollup.status_minutes.items()},
                "night_minutes": str(rollup.night_minutes),
                "row_count": rollup.row_count,
            }
        )
        if len(out) >= limit:
            break
    return {"source": str(csv_path), "rollups": out}
