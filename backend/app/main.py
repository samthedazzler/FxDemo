import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

PACKAGES_DIR = os.path.join(BASE_DIR, "packages")

sys.path.append(PACKAGES_DIR)

from fastapi import FastAPI, UploadFile

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


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )