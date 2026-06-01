"""Seed script — populates a fresh database with the section 5.2 worked
example plus a handful of additional agents covering each leave policy and
each contract type.

Usage:
    python seed_data.py
"""

from datetime import date
from decimal import Decimal

from app.database import Base, SessionLocal, engine
from app.models.db import Agent, HolidayCalendar, LeaveLedger
from app.models.enums import ContractType, LeaveType, OverspendPolicy


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # --- Section 5.2 worked-example agent ---
        if db.query(Agent).filter(Agent.agent_id == "WORKED_EXAMPLE").first() is None:
            db.add(
                Agent(
                    agent_id="WORKED_EXAMPLE",
                    contract_type=ContractType.FULL_TIME,
                    base_hourly_rate=Decimal("250"),
                    min_monthly_pay=Decimal("35000"),
                    max_monthly_pay=Decimal("70000"),
                    weekly_contracted_hours=40,
                    overtime_multiplier=Decimal("1.5"),
                    holiday_multiplier=Decimal("2.0"),
                    night_differential=Decimal("0.10"),
                    currency="INR",
                    primary_site="Teleperformance-Dublin",
                )
            )

        # --- Real agent IDs from the supplied CSV (Teleperformance Dublin) ---
        sample_agents = [
            ("61581666459416", ContractType.FULL_TIME, OverspendPolicy.UNPAID_AUTO),
            ("61581635771227", ContractType.FULL_TIME, OverspendPolicy.MANAGER_APPROVAL),
            ("61580771977862", ContractType.PART_TIME, OverspendPolicy.UNPAID_AUTO),
            ("61581055615480", ContractType.FULL_TIME, OverspendPolicy.UNPAID_AUTO),
            ("CONTRACTOR_001", ContractType.CONTRACTOR, OverspendPolicy.BLOCK),
        ]

        for agent_id, contract_type, policy in sample_agents:
            if db.query(Agent).filter(Agent.agent_id == agent_id).first() is not None:
                continue
            db.add(
                Agent(
                    agent_id=agent_id,
                    contract_type=contract_type,
                    base_hourly_rate=Decimal("28.00") if contract_type == ContractType.CONTRACTOR else Decimal("18.50"),
                    min_monthly_pay=Decimal("0") if contract_type == ContractType.CONTRACTOR else Decimal("1800"),
                    max_monthly_pay=None if contract_type == ContractType.CONTRACTOR else Decimal("5000"),
                    weekly_contracted_hours=40 if contract_type != ContractType.PART_TIME else 20,
                    overtime_multiplier=Decimal("1.5"),
                    holiday_multiplier=Decimal("2.0"),
                    night_differential=Decimal("0.10"),
                    currency="EUR",
                    primary_site="Teleperformance-Dublin",
                )
            )
            db.flush()
            db.add(
                LeaveLedger(
                    agent_id=agent_id,
                    leave_type=LeaveType.PAID,
                    approved_balance=Decimal("20"),
                    consumed_balance=Decimal("0"),
                    overspend_policy=policy,
                    cycle_start=date(2026, 1, 1),
                )
            )
            db.add(
                LeaveLedger(
                    agent_id=agent_id,
                    leave_type=LeaveType.SICK,
                    approved_balance=Decimal("10"),
                    consumed_balance=Decimal("0"),
                    overspend_policy=OverspendPolicy.UNPAID_AUTO,
                    cycle_start=date(2026, 1, 1),
                )
            )

        # Holiday calendar (per-site)
        if (
            db.query(HolidayCalendar)
            .filter(HolidayCalendar.site == "Teleperformance-Dublin", HolidayCalendar.date == date(2026, 3, 17))
            .first()
            is None
        ):
            db.add(
                HolidayCalendar(
                    site="Teleperformance-Dublin",
                    date=date(2026, 3, 17),
                    name="St Patrick's Day",
                )
            )

        db.commit()
        print("Seed complete. Agents loaded:", db.query(Agent).count())
    finally:
        db.close()


if __name__ == "__main__":
    seed()
