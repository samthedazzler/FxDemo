import os
import asyncio
import sys
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
PROJECT_ROOT = Path(BASE_DIR).parent
DATA_DIR = PROJECT_ROOT / "Data"

PACKAGES_DIR = os.path.join(BASE_DIR, "packages")

sys.path.append(PACKAGES_DIR)

from fastapi import FastAPI, UploadFile, WebSocket, WebSocketDisconnect

app = FastAPI(
    title="FxDemo Embedded API",
    version="1.0.0"
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/csv/summary")
async def csv_summary(file: UploadFile) -> dict[str, int | str]:

    content = await file.read()

    text = content.decode("utf-8-sig")

    rows = [
        line
        for line in text.splitlines()
        if line.strip()
    ]

    return {
        "filename": file.filename or "uploaded.csv",

        "rows": max(len(rows) - 1, 0),

        "columns": len(rows[0].split(",")) if rows else 0,
    }


def csv_snapshot() -> dict[str, float]:
    DATA_DIR.mkdir(exist_ok=True)

    snapshot: dict[str, float] = {}
    for csv_file in DATA_DIR.glob("*.csv"):
        if csv_file.is_file():
            stat = csv_file.stat()
            snapshot[csv_file.name] = stat.st_mtime
    return snapshot


@app.websocket("/ws/csv-watch")
async def csv_watch(websocket: WebSocket) -> None:
    await websocket.accept()
    last_snapshot = csv_snapshot()
    await websocket.send_json({
        "event": "initial",
        "csv_count": len(last_snapshot),
        "files": sorted(last_snapshot.keys()),
    })

    try:
        while True:
            await asyncio.sleep(1)
            current_snapshot = csv_snapshot()
            if current_snapshot != last_snapshot:
                last_snapshot = current_snapshot
                await websocket.send_json({
                    "event": "csv_changed",
                    "csv_count": len(current_snapshot),
                    "files": sorted(current_snapshot.keys()),
                })
    except WebSocketDisconnect:
        return


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
