"""Section 8 — Auditability. Deterministic content hash of input record.

If any input changes (e.g. WFM corrects a worked_minutes value), the
recomputed record gets a new hash, and the chain of corrections is visible
in the audit log via FinancialBreakdown.parent_id.
"""

import hashlib
import json
from decimal import Decimal
from datetime import date, datetime
from typing import Any


def _default(o: Any) -> Any:
    if isinstance(o, Decimal):
        return f"{o:.6f}".rstrip("0").rstrip(".")
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(f"Not serializable: {type(o)}")


def content_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=_default, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
