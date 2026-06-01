"""Section 11 Appendix — Status to Pay Category mapping coverage."""

from app.models.enums import PayCategory
from app.utils.status_mapping import classify_status, all_mappings


def test_appendix_mapping_complete():
    rows = {m.wfm_status for m in all_mappings()}
    expected = {
        "chat",
        "email",
        "email_backlog",
        "after_contact_work",
        "available",
        "break",
        "lunch",
        "facebook_training_meeting",
    }
    assert expected.issubset(rows)


def test_productive_statuses_route_to_productive():
    for s in ("chat", "email", "email_backlog", "after_contact_work"):
        assert classify_status(s).pay_category == PayCategory.REGULAR_PRODUCTIVE


def test_available_is_paid_idle():
    assert classify_status("available").pay_category == PayCategory.REGULAR_PAID_IDLE


def test_break_and_lunch_are_shrinkage():
    assert classify_status("break").pay_category == PayCategory.COMPENSABLE_SHRINKAGE
    assert classify_status("lunch").pay_category == PayCategory.COMPENSABLE_SHRINKAGE
    assert classify_status("lunch").billable is False  # typically unpaid


def test_training_routes_to_training():
    assert classify_status("facebook_training_meeting").pay_category == PayCategory.TRAINING


def test_unknown_status_falls_to_unpaid():
    assert classify_status("system_outage").pay_category == PayCategory.UNPAID
