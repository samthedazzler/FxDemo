"""Section 3.1 — WFM Aggregator component (Operations-owned).

Bucketizes agent activity by Status into productive / available / shrinkage /
training minutes per interval, using the Section 11 Appendix mapping.

This module produces an `HourlyBreakdownIn` payload that the Billing Engine
can consume directly.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, Optional

from app.config import settings
from app.models.enums import PayCategory
from app.schemas.breakdown import HourlyBreakdownIn
from app.utils.status_mapping import classify_status


def aggregate_status_map(
    agent_id: str,
    work_date: date,
    status_minutes: Dict[str, float],
    scheduled_minutes: Decimal,
    is_holiday: bool = False,
    night_minutes: Decimal = Decimal("0"),
    site: Optional[str] = None,
) -> HourlyBreakdownIn:
    """Roll up a map of {WFM Status: minutes} into the daily breakdown record.

    Routing (section 11):
      productive  <- chat, email, email_backlog, after_contact_work, available
      shrinkage   <- break, lunch
      training    <- facebook_training_meeting
      worked      = productive + available (per section 4.3 comment)
      overtime    = max(0, worked - scheduled)
    """
    productive = Decimal("0")
    available = Decimal("0")
    breaks = Decimal("0")
    training = Decimal("0")

    for status, minutes in status_minutes.items():
        m = Decimal(str(minutes))
        entry = classify_status(status)
        if entry.pay_category == PayCategory.REGULAR_PRODUCTIVE:
            productive += m
        elif entry.pay_category == PayCategory.REGULAR_PAID_IDLE:
            available += m
        elif entry.pay_category == PayCategory.COMPENSABLE_SHRINKAGE:
            breaks += m
        elif entry.pay_category == PayCategory.TRAINING:
            training += m
        # PayCategory.UNPAID is dropped from worked time on purpose.

    worked = productive + available
    overtime = max(Decimal("0"), worked - scheduled_minutes)

    return HourlyBreakdownIn(
        agent_id=agent_id,
        date=work_date,
        productive_minutes=productive,
        available_minutes=available,
        break_minutes=breaks,
        training_minutes=training,
        scheduled_minutes=scheduled_minutes,
        worked_minutes=worked,
        overtime_minutes=overtime,
        is_holiday=is_holiday,
        night_minutes=night_minutes,
        source_status_breakdown={k: float(v) for k, v in status_minutes.items()},
        site=site,
    )
