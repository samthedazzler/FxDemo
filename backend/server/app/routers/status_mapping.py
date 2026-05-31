"""Section 11 Appendix — Status -> Pay Category Mapping (read-only)."""

from typing import List

from fastapi import APIRouter

from app.schemas.status_mapping import StatusMappingEntry
from app.utils.status_mapping import all_mappings, classify_status

router = APIRouter(prefix="/status-mapping", tags=["Status Mapping (Appendix)"])


@router.get("", response_model=List[StatusMappingEntry])
def list_mappings():
    return all_mappings()


@router.get("/{wfm_status}", response_model=StatusMappingEntry)
def classify(wfm_status: str):
    return classify_status(wfm_status)
