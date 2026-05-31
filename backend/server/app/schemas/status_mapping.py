from pydantic import BaseModel

from app.models.enums import PayCategory


class StatusMappingEntry(BaseModel):
    """Section 11 Appendix — Status -> Pay Category mapping (one row)."""

    wfm_status: str
    pay_category: PayCategory
    billable: bool
    notes: str
