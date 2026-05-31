from datetime import datetime, date

from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import (
    ContractType,
    LeaveType,
    OverspendPolicy,
    DeltaReason,
    MinMaxStatus,
    BillingStatus,
    ReconciliationCheckType,
)


class Agent(Base):
    """Section 4.1 Agent Master (HR-owned)."""

    __tablename__ = "agent_master"

    agent_id = Column(String, primary_key=True)
    contract_type = Column(SAEnum(ContractType), nullable=False)
    base_hourly_rate = Column(Numeric(12, 4), nullable=False)
    min_monthly_pay = Column(Numeric(12, 2), nullable=False, default=0)
    max_monthly_pay = Column(Numeric(12, 2), nullable=True)
    weekly_contracted_hours = Column(Integer, nullable=False, default=40)
    overtime_multiplier = Column(Numeric(6, 4), nullable=False, default=1.5)
    holiday_multiplier = Column(Numeric(6, 4), nullable=False, default=2.0)
    night_differential = Column(Numeric(6, 4), nullable=False, default=0.10)
    currency = Column(String(3), nullable=False, default="INR")
    primary_site = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    leaves = relationship("LeaveLedger", back_populates="agent", cascade="all, delete-orphan")


class LeaveLedger(Base):
    """Section 4.2 Leave Ledger (HR-owned)."""

    __tablename__ = "leave_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agent_master.agent_id"), nullable=False)
    leave_type = Column(SAEnum(LeaveType), nullable=False)
    approved_balance = Column(Numeric(8, 2), nullable=False, default=0)
    consumed_balance = Column(Numeric(8, 2), nullable=False, default=0)
    overspend_policy = Column(SAEnum(OverspendPolicy), nullable=False, default=OverspendPolicy.UNPAID_AUTO)
    cycle_start = Column(Date, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    agent = relationship("Agent", back_populates="leaves")

    __table_args__ = (
        UniqueConstraint("agent_id", "leave_type", "cycle_start", name="uq_agent_leavetype_cycle"),
    )

    @property
    def remaining_balance(self) -> float:
        return float(self.approved_balance) - float(self.consumed_balance)


class HourlyBreakdown(Base):
    """Section 4.3 Hourly Breakdown Input (from WFM)."""

    __tablename__ = "hourly_breakdown"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agent_master.agent_id"), nullable=False)
    date = Column(Date, nullable=False)
    productive_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    available_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    break_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    training_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    scheduled_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    worked_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    overtime_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    is_holiday = Column(Boolean, nullable=False, default=False)
    night_minutes = Column(Numeric(8, 2), nullable=False, default=0)
    source_status_breakdown = Column(JSON, nullable=True)
    site = Column(String, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("agent_id", "date", name="uq_agent_date_breakdown"),
        Index("ix_breakdown_agent_date", "agent_id", "date"),
    )


class FinancialBreakdown(Base):
    """Output of Billing Engine. One record per agent per day.

    Carries full provenance (Section 8 — Auditability) so any disputed
    amount can be replayed deterministically.
    """

    __tablename__ = "financial_breakdown"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agent_master.agent_id"), nullable=False)
    date = Column(Date, nullable=False)

    # Pay components (section 5.1 step 3)
    regular_pay = Column(Numeric(12, 4), nullable=False, default=0)
    overtime_pay = Column(Numeric(12, 4), nullable=False, default=0)
    holiday_pay = Column(Numeric(12, 4), nullable=False, default=0)
    night_premium = Column(Numeric(12, 4), nullable=False, default=0)
    leave_pay = Column(Numeric(12, 4), nullable=False, default=0)

    daily_gross = Column(Numeric(12, 4), nullable=False, default=0)
    month_to_date_gross = Column(Numeric(12, 4), nullable=False, default=0)
    projected_monthly_gross = Column(Numeric(12, 4), nullable=False, default=0)

    monthly_pay = Column(Numeric(12, 4), nullable=True)
    delta_reason = Column(SAEnum(DeltaReason), nullable=False, default=DeltaReason.NONE)
    min_max_status = Column(SAEnum(MinMaxStatus), nullable=False, default=MinMaxStatus.WITHIN_BOUNDS)
    billing_status = Column(SAEnum(BillingStatus), nullable=False, default=BillingStatus.FINALIZED)

    currency = Column(String(3), nullable=False, default="INR")

    # Section 8 — content hash of inputs + corrections chain
    content_hash = Column(String(64), nullable=False)
    parent_id = Column(Integer, ForeignKey("financial_breakdown.id"), nullable=True)
    rate_card_version = Column(String, nullable=True)
    provenance = Column(JSON, nullable=False)
    alerts = Column(JSON, nullable=False, default=list)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_financial_agent_date", "agent_id", "date"),
    )


class PendingApproval(Base):
    """Section 6.3 MANAGER_APPROVAL queue. Holds absences awaiting manager review."""

    __tablename__ = "pending_approval"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, ForeignKey("agent_master.agent_id"), nullable=False)
    date = Column(Date, nullable=False)
    leave_type = Column(SAEnum(LeaveType), nullable=True)
    reason = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")
    manager_id = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("agent_id", "date", name="uq_pending_agent_date"),
    )


class ReconciliationFinding(Base):
    """Section 6.4 Daily Reconciliation findings."""

    __tablename__ = "reconciliation_finding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_date = Column(Date, nullable=False)
    check_type = Column(SAEnum(ReconciliationCheckType), nullable=False)
    agent_id = Column(String, nullable=True)
    severity = Column(String, nullable=False, default="WARN")
    message = Column(String, nullable=False)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    """Section 8 — Auditability. Provenance log for every Billing Engine
    computation, replay, and override."""

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)
    target_id = Column(String, nullable=True)
    content_hash = Column(String(64), nullable=True)
    parent_hash = Column(String(64), nullable=True)
    payload = Column(JSON, nullable=False)
    actor = Column(String, nullable=False, default="system")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class HolidayCalendar(Base):
    """Section 10 — Holiday calendar is per-site, not global. Multi-site agents
    resolve by primary site."""

    __tablename__ = "holiday_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    name = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("site", "date", name="uq_site_date_holiday"),
    )


class RateCardVersion(Base):
    """Section 10 — Rate Card service emits a version_id; previews older than
    24h are recomputed."""

    __tablename__ = "rate_card_version"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(String, nullable=False, unique=True)
    agent_id = Column(String, ForeignKey("agent_master.agent_id"), nullable=False)
    snapshot = Column(JSON, nullable=False)
    effective_from = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
