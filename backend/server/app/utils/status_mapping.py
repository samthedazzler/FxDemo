"""Section 11 Appendix: Status -> Pay Category Mapping.

Single source of truth used by both the WFM Aggregator (to bucketize raw
status rows into productive / shrinkage / training / idle minutes) and by
the read-only `/status-mapping` endpoint that the Java frontend renders.
"""

from typing import Dict

from app.models.enums import PayCategory
from app.schemas.status_mapping import StatusMappingEntry

# Mirrors the table on page 10 of the design doc.
STATUS_TO_PAY_CATEGORY: Dict[str, StatusMappingEntry] = {
    "chat": StatusMappingEntry(
        wfm_status="chat",
        pay_category=PayCategory.REGULAR_PRODUCTIVE,
        billable=True,
        notes="Yes - full rate",
    ),
    "email": StatusMappingEntry(
        wfm_status="email",
        pay_category=PayCategory.REGULAR_PRODUCTIVE,
        billable=True,
        notes="Yes - full rate",
    ),
    "email_backlog": StatusMappingEntry(
        wfm_status="email_backlog",
        pay_category=PayCategory.REGULAR_PRODUCTIVE,
        billable=True,
        notes="Yes - full rate",
    ),
    "after_contact_work": StatusMappingEntry(
        wfm_status="after_contact_work",
        pay_category=PayCategory.REGULAR_PRODUCTIVE,
        billable=True,
        notes="Yes - full rate",
    ),
    "available": StatusMappingEntry(
        wfm_status="available",
        pay_category=PayCategory.REGULAR_PAID_IDLE,
        billable=True,
        notes="Yes - full rate",
    ),
    "break": StatusMappingEntry(
        wfm_status="break",
        pay_category=PayCategory.COMPENSABLE_SHRINKAGE,
        billable=True,
        notes="Yes - paid, capped per shift",
    ),
    "lunch": StatusMappingEntry(
        wfm_status="lunch",
        pay_category=PayCategory.COMPENSABLE_SHRINKAGE,
        billable=False,
        notes="Depends on contract; typically unpaid",
    ),
    "facebook_training_meeting": StatusMappingEntry(
        wfm_status="facebook_training_meeting",
        pay_category=PayCategory.TRAINING,
        billable=True,
        notes="Yes - full rate, charged to training cost center",
    ),
}


PRODUCTIVE_CATEGORIES = {PayCategory.REGULAR_PRODUCTIVE, PayCategory.REGULAR_PAID_IDLE}


def classify_status(status: str) -> StatusMappingEntry:
    """Return the mapping row for an arbitrary WFM Status.

    Unknown statuses default to UNPAID (raises visibility instead of silently
    paying for an unrecognised activity).
    """
    if status in STATUS_TO_PAY_CATEGORY:
        return STATUS_TO_PAY_CATEGORY[status]
    return StatusMappingEntry(
        wfm_status=status,
        pay_category=PayCategory.UNPAID,
        billable=False,
        notes="Unmapped status - review with Ops",
    )


def all_mappings() -> list[StatusMappingEntry]:
    return list(STATUS_TO_PAY_CATEGORY.values())
