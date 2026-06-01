"""Streaming CSV ingest tests."""

from decimal import Decimal
from io import StringIO
from textwrap import dedent

from app.services import csv_ingest


CSV_HEADER = (
    "Agent Id,Status,GROUP VIEW PERMISSION FILTER,Interval Start Time ,SRT Team,"
    "Vendor Site,local_interval_sta,Pst Interval Start,Utc Interval Start,"
    "Number of Records,time_in_interval_m,dummy,Empty Extract ,"
    "Interval Start Time  (copy),Last Update Ts,Local End Time,Local Interval End,"
    "Local Start Time,Organization,Pst Interval End,pst_end_time,pst_start_time,"
    "Status Group,Utc End Time,Utc Interval End,Utc Start Time"
)


def _row(
    agent_id: str,
    status: str,
    minutes: str,
    local_interval_start: str = "4/12/2026 10:00:00 AM",
    local_start_time: str = "4/12/2026 10:28:38 AM",
    site: str = "Teleperformance-Dublin",
) -> str:
    # Column order MUST match CSV_HEADER:
    # 1=Agent Id 2=Status 3=GVPF 4=Interval Start Time 5=SRT Team 6=Vendor Site
    # 7=local_interval_sta 8=Pst Interval Start 9=Utc Interval Start
    # 10=Number of Records 11=time_in_interval_m 12=dummy 13=Empty Extract
    # 14=Interval Start Time (copy) 15=Last Update Ts 16=Local End Time
    # 17=Local Interval End 18=Local Start Time 19=Organization 20-26 timezones
    return (
        f"{agent_id},{status},True,4/12/2026 9:00:00 AM,Team,{site},"
        f"{local_interval_start},4/12/2026 2:00:00 AM,4/12/2026 9:00:00 AM,"
        f"1,{minutes},1,True,4/12/2026 9:00:00 AM,4/13/2026 11:24:48 PM,"
        f"4/12/2026 10:28:43 AM,4/12/2026 10:30:00 AM,{local_start_time},"
        f"Teleperformance,4/12/2026 2:30:00 AM,4/12/2026 2:28:43 AM,"
        f"4/12/2026 2:28:38 AM,OCC,4/12/2026 9:28:43 AM,4/12/2026 9:30:00 AM,"
        f"4/12/2026 9:28:38 AM"
    )


def _csv_text(rows: list[str]) -> str:
    return CSV_HEADER + "\n" + "\n".join(rows) + "\n"


def test_aggregates_minutes_per_status_for_single_agent_day():
    text = _csv_text(
        [
            _row("A1", "chat", "10.0", local_interval_start="4/12/2026 10:00:00 AM"),
            _row("A1", "chat", "5.5", local_interval_start="4/12/2026 10:00:00 AM"),
            _row("A1", "available", "20.0", local_interval_start="4/12/2026 10:00:00 AM"),
            _row("A1", "break", "15.0", local_interval_start="4/12/2026 10:00:00 AM"),
        ]
    )
    rollups = list(csv_ingest.stream_rollups(StringIO(text)))
    assert len(rollups) == 1
    r = rollups[0]
    assert r.agent_id == "A1"
    assert r.status_minutes["chat"] == Decimal("15.5")
    assert r.status_minutes["available"] == Decimal("20.0")
    assert r.status_minutes["break"] == Decimal("15.0")
    assert r.row_count == 4
    assert r.site == "Teleperformance-Dublin"


def test_emits_one_rollup_per_agent_day():
    text = _csv_text(
        [
            _row("A1", "chat", "10"),
            _row("A2", "chat", "20"),
            _row("A1", "email", "5", local_interval_start="4/13/2026 10:00:00 AM",
                 local_start_time="4/13/2026 10:00:00 AM"),
        ]
    )
    rollups = list(csv_ingest.stream_rollups(StringIO(text)))
    assert len(rollups) == 3
    keys = {(r.agent_id, r.work_date.isoformat()) for r in rollups}
    assert keys == {
        ("A1", "2026-04-12"),
        ("A1", "2026-04-13"),
        ("A2", "2026-04-12"),
    }


def test_night_window_detection():
    # 23:00 local — inside the 22-06 window
    text = _csv_text(
        [
            _row(
                "A1",
                "chat",
                "30",
                local_interval_start="4/12/2026 11:00:00 PM",
                local_start_time="4/12/2026 11:05:00 PM",
            ),
            _row(
                "A1",
                "chat",
                "20",
                local_interval_start="4/12/2026 11:00:00 PM",
                local_start_time="4/12/2026 11:45:00 PM",
            ),
            # 14:00 — daytime, should NOT count
            _row(
                "A1",
                "chat",
                "100",
                local_interval_start="4/12/2026 11:00:00 PM",
                local_start_time="4/12/2026 2:00:00 PM",
            ),
        ]
    )
    rollups = list(csv_ingest.stream_rollups(StringIO(text)))
    assert len(rollups) == 1
    assert rollups[0].night_minutes == Decimal("50")
    # Total minutes still summed correctly
    assert rollups[0].status_minutes["chat"] == Decimal("150")


def test_only_agent_id_filter():
    text = _csv_text(
        [
            _row("KEEP", "chat", "10"),
            _row("DROP", "chat", "10"),
        ]
    )
    rollups = list(csv_ingest.stream_rollups(StringIO(text), only_agent_id="KEEP"))
    assert len(rollups) == 1
    assert rollups[0].agent_id == "KEEP"


def test_zero_or_blank_minutes_are_ignored():
    text = _csv_text(
        [
            _row("A1", "chat", "0"),
            _row("A1", "chat", ""),
            _row("A1", "chat", "12.5"),
        ]
    )
    rollups = list(csv_ingest.stream_rollups(StringIO(text)))
    assert len(rollups) == 1
    assert rollups[0].status_minutes["chat"] == Decimal("12.5")
    assert rollups[0].row_count == 1


def test_csv_with_bom_and_trailing_header_whitespace_handled():
    # Realistic header from the source file
    text = "﻿" + _csv_text([_row("A1", "chat", "5")])
    rollups = list(csv_ingest.stream_rollups(StringIO(text)))
    assert len(rollups) == 1
    assert rollups[0].status_minutes["chat"] == Decimal("5")
