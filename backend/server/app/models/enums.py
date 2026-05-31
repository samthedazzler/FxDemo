from enum import Enum


class ContractType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACTOR = "CONTRACTOR"


class LeaveType(str, Enum):
    PAID = "PAID"
    SICK = "SICK"
    UNPAID = "UNPAID"
    COMP_OFF = "COMP_OFF"
    BEREAVEMENT = "BEREAVEMENT"


class OverspendPolicy(str, Enum):
    BLOCK = "BLOCK"
    UNPAID_AUTO = "UNPAID_AUTO"
    MANAGER_APPROVAL = "MANAGER_APPROVAL"


class PayCategory(str, Enum):
    REGULAR_PRODUCTIVE = "regular productive"
    REGULAR_PAID_IDLE = "regular paid (idle)"
    COMPENSABLE_SHRINKAGE = "compensable shrinkage"
    TRAINING = "training"
    UNPAID = "unpaid"


class DeltaReason(str, Enum):
    MIN_FLOOR_APPLIED = "MIN_FLOOR_APPLIED"
    MAX_CAP_APPLIED = "MAX_CAP_APPLIED"
    NONE = "NONE"


class MinMaxStatus(str, Enum):
    WITHIN_BOUNDS = "WITHIN_BOUNDS"
    FLOOR_APPLIED = "FLOOR_APPLIED"
    CAP_APPLIED = "CAP_APPLIED"


class BillingStatus(str, Enum):
    FINALIZED = "FINALIZED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    BLOCKED = "BLOCKED"
    UNPAID_LWP = "UNPAID_LWP"


class ReconciliationCheckType(str, Enum):
    COVERAGE = "COVERAGE"
    LEAVE_INTEGRITY = "LEAVE_INTEGRITY"
    PREVIEW_VS_ACTUAL = "PREVIEW_VS_ACTUAL"


# Section 11: WFM Status -> Pay Category mapping (Appendix)
class WFMStatus(str, Enum):
    CHAT = "chat"
    EMAIL = "email"
    EMAIL_BACKLOG = "email_backlog"
    AFTER_CONTACT_WORK = "after_contact_work"
    AVAILABLE = "available"
    BREAK = "break"
    LUNCH = "lunch"
    FACEBOOK_TRAINING_MEETING = "facebook_training_meeting"
