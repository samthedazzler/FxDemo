"""Section 6.4 — The Daily Reconciliation.

Every night, the Reconciliation Service runs three checks:
  1. Coverage check       — scheduled hours vs worked hours per agent.
                            Variances over a threshold (default 10%) flagged.
  2. Leave balance integrity — sum of consumed leaves in WFM equals the
                            decrements in the Leave Ledger. Drift => sync bug.
  3. Cost preview vs actual — if Ops approved OT with a preview cost, compare
                            against the actual cost computed post-shift.
                            Drift => rate card may be stale.

Also surfaces section 10 mitigations:
  - Daily reconciliation job; alert if drift exceeds 0.5 leave-day per agent.
  - Pending approvals are reported here (section 6.3 — prevents month-close).
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db import (
    FinancialBreakdown,
    HourlyBreakdown,
    LeaveLedger,
    PendingApproval,
    ReconciliationFinding,
)
from app.models.enums import BillingStatus, ReconciliationCheckType


def _coverage_check(db: Session, run_date: date) -> List[ReconciliationFinding]:
    findings: List[ReconciliationFinding] = []
    rows = db.query(HourlyBreakdown).filter(HourlyBreakdown.date == run_date).all()
    threshold = Decimal(str(settings.coverage_variance_threshold_pct)) / Decimal("100")
    for r in rows:
        scheduled = Decimal(r.scheduled_minutes)
        worked = Decimal(r.worked_minutes)
        if scheduled <= 0:
            continue
        variance = abs(worked - scheduled) / scheduled
        if variance > threshold:
            findings.append(
                ReconciliationFinding(
                    run_date=run_date,
                    check_type=ReconciliationCheckType.COVERAGE,
                    agent_id=r.agent_id,
                    severity="WARN",
                    message=(
                        f"Coverage variance {variance:.1%} exceeds threshold "
                        f"{settings.coverage_variance_threshold_pct}%."
                    ),
                    details={
                        "scheduled_minutes": str(scheduled),
                        "worked_minutes": str(worked),
                        "variance_pct": f"{variance:.4f}",
                    },
                )
            )
    return findings


def _leave_integrity_check(db: Session, run_date: date) -> List[ReconciliationFinding]:
    findings: List[ReconciliationFinding] = []
    drift_threshold = Decimal(str(settings.leave_drift_threshold_days))

    # Count days where WFM saw worked_minutes==0 AND scheduled_minutes>0 (i.e. an
    # absence) per agent vs the ledger consumed_balance for that agent.
    agents = db.query(LeaveLedger.agent_id).distinct().all()
    for (agent_id,) in agents:
        wfm_absences = (
            db.query(HourlyBreakdown)
            .filter(
                HourlyBreakdown.agent_id == agent_id,
                HourlyBreakdown.worked_minutes == 0,
                HourlyBreakdown.scheduled_minutes > 0,
            )
            .count()
        )
        ledger_consumed = (
            db.query(LeaveLedger)
            .filter(LeaveLedger.agent_id == agent_id)
            .all()
        )
        ledger_total = sum((Decimal(l.consumed_balance) for l in ledger_consumed), Decimal("0"))
        drift = abs(Decimal(wfm_absences) - ledger_total)
        if drift > drift_threshold:
            findings.append(
                ReconciliationFinding(
                    run_date=run_date,
                    check_type=ReconciliationCheckType.LEAVE_INTEGRITY,
                    agent_id=agent_id,
                    severity="WARN",
                    message=(
                        f"Leave drift of {drift} day(s) between WFM absences and ledger consumed "
                        "balance — possible sync bug."
                    ),
                    details={
                        "wfm_absences": wfm_absences,
                        "ledger_consumed_total": str(ledger_total),
                        "drift_days": str(drift),
                    },
                )
            )
    return findings


def _preview_vs_actual_check(db: Session, run_date: date) -> List[ReconciliationFinding]:
    """If an OT preview was issued for the day, compare the previewed cost to
    the actual recorded cost. We treat actual overtime_pay + night_premium as
    "OT cost"."""
    findings: List[ReconciliationFinding] = []
    rows = (
        db.query(FinancialBreakdown)
        .filter(FinancialBreakdown.date == run_date)
        .all()
    )
    for r in rows:
        prev = (r.provenance or {}).get("preview_cost")
        if prev is None:
            continue
        actual = Decimal(r.overtime_pay) + Decimal(r.night_premium)
        previewed = Decimal(str(prev))
        if previewed == 0:
            continue
        drift = abs(actual - previewed) / previewed
        if drift > Decimal("0.05"):  # 5% drift threshold
            findings.append(
                ReconciliationFinding(
                    run_date=run_date,
                    check_type=ReconciliationCheckType.PREVIEW_VS_ACTUAL,
                    agent_id=r.agent_id,
                    severity="WARN",
                    message=(
                        f"OT preview vs actual drift {drift:.1%}. Rate card may be stale."
                    ),
                    details={
                        "previewed": str(previewed),
                        "actual": str(actual),
                    },
                )
            )
    return findings


def _pending_close_block(db: Session, run_date: date) -> List[ReconciliationFinding]:
    """Section 6.3 — month-close cannot proceed while any MANAGER_APPROVAL
    pending."""
    findings: List[ReconciliationFinding] = []
    rows = (
        db.query(PendingApproval)
        .filter(PendingApproval.status == "PENDING")
        .all()
    )
    for p in rows:
        if p.date.month == run_date.month and p.date.year == run_date.year:
            findings.append(
                ReconciliationFinding(
                    run_date=run_date,
                    check_type=ReconciliationCheckType.LEAVE_INTEGRITY,
                    agent_id=p.agent_id,
                    severity="BLOCK",
                    message=(
                        f"Pending MANAGER_APPROVAL on {p.date} — month-close blocked."
                    ),
                    details={"pending_id": p.id, "leave_type": p.leave_type.value if p.leave_type else None},
                )
            )
    return findings


def run(db: Session, run_date: date) -> dict:
    """Execute all 6.4 checks. Persist findings and return a summary."""
    findings: List[ReconciliationFinding] = []
    findings.extend(_coverage_check(db, run_date))
    leave_findings = _leave_integrity_check(db, run_date)
    leave_findings.extend(_pending_close_block(db, run_date))
    findings.extend(leave_findings)
    findings.extend(_preview_vs_actual_check(db, run_date))

    for f in findings:
        db.add(f)
    db.commit()
    for f in findings:
        db.refresh(f)

    coverage_count = sum(1 for f in findings if f.check_type == ReconciliationCheckType.COVERAGE)
    leave_count = sum(1 for f in findings if f.check_type == ReconciliationCheckType.LEAVE_INTEGRITY)
    preview_count = sum(
        1 for f in findings if f.check_type == ReconciliationCheckType.PREVIEW_VS_ACTUAL
    )

    return {
        "run_date": run_date,
        "coverage_findings": coverage_count,
        "leave_integrity_findings": leave_count,
        "preview_vs_actual_findings": preview_count,
        "total_findings": len(findings),
        "findings": findings,
    }
