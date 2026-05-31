"""Section 8 — Auditability & Compliance.

Writes a full provenance record for every Billing Engine computation,
correction, and override. Each FinancialBreakdown row carries a content
hash; corrections create new records with parent reference, original
preserved (section 10 risk mitigation: "Backfill of corrections poisons
month-end").
"""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.db import AuditLog


def log_event(
    db: Session,
    event_type: str,
    payload: Dict[str, Any],
    agent_id: Optional[str] = None,
    target_id: Optional[str] = None,
    content_hash: Optional[str] = None,
    parent_hash: Optional[str] = None,
    actor: str = "system",
) -> AuditLog:
    entry = AuditLog(
        event_type=event_type,
        agent_id=agent_id,
        target_id=target_id,
        content_hash=content_hash,
        parent_hash=parent_hash,
        payload=payload,
        actor=actor,
    )
    db.add(entry)
    db.flush()
    return entry
