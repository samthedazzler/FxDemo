# Embedded FastAPI Backend

The JavaFX app starts this FastAPI service automatically with:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Install the Python dependencies once before running the JavaFX app:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.txt
```

The app checks `.\.venv\Scripts\python.exe` first, then falls back to `python` on `PATH`.
