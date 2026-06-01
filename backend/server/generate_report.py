"""Generate WFM_Finance_Implementation_Report.pdf.

Run with:  python generate_report.py
Output:    ../WFM_Finance_Implementation_Report.pdf  (next to the design doc)
"""

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


# ----- Style palette (mirrors the design-doc look: deep blue headings + grey rules) ----- #
BRAND = colors.HexColor("#1F3A68")
SUB = colors.HexColor("#2C5F8D")
ROW_ALT = colors.HexColor("#F2F5FA")
BORDER = colors.HexColor("#D0D7E2")
MUTED = colors.HexColor("#5A6675")
ACCENT = colors.HexColor("#E8EEF7")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=26, leading=32, textColor=BRAND, alignment=TA_CENTER, spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Title"], fontName="Helvetica",
            fontSize=14, leading=18, textColor=SUB, alignment=TA_CENTER, spaceAfter=4,
        ),
        "subtitle_italic": ParagraphStyle(
            "subtitle_italic", parent=base["Title"], fontName="Helvetica-Oblique",
            fontSize=11, leading=14, textColor=MUTED, alignment=TA_CENTER, spaceAfter=20,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=18, leading=22, textColor=BRAND, spaceBefore=16, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=13, leading=16, textColor=SUB, spaceBefore=12, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=SUB, spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10, leading=14, textColor=colors.black, alignment=TA_JUSTIFY, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10, leading=14, leftIndent=14, bulletIndent=2, spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "code", parent=base["BodyText"], fontName="Courier",
            fontSize=9, leading=12, leftIndent=10, textColor=colors.HexColor("#222"),
            backColor=ACCENT, borderPadding=6, spaceBefore=4, spaceAfter=8,
        ),
        "callout": ParagraphStyle(
            "callout", parent=base["BodyText"], fontName="Helvetica-Oblique",
            fontSize=10, leading=14, textColor=MUTED, leftIndent=14, spaceAfter=8,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8, leading=10, textColor=MUTED, alignment=TA_CENTER,
        ),
        "table_h": ParagraphStyle(
            "table_h", fontName="Helvetica-Bold", fontSize=9, leading=12,
            textColor=colors.white,
        ),
        "table_b": ParagraphStyle(
            "table_b", fontName="Helvetica", fontSize=9, leading=12,
            textColor=colors.black,
        ),
    }


S = _styles()


def styled_table(data, col_widths=None, repeat_header=True):
    """Boxed table with a brand-blue header row and zebra striping."""
    wrapped = [[Paragraph(c, S["table_h"]) if i == 0 else Paragraph(c, S["table_b"])
                for c in row] for i, row in enumerate(data)]
    t = Table(wrapped, colWidths=col_widths, repeatRows=1 if repeat_header else 0)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for r in range(1, len(data)):
        if r % 2 == 0:
            style.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
    t.setStyle(TableStyle(style))
    return t


def bullet(text):
    return Paragraph(f"•&nbsp;&nbsp;{text}", S["bullet"])


def code(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("\n", "<br/>").replace(" ", "&nbsp;")
    return Paragraph(text, S["code"])


def on_page(canvas, doc):
    """Header band + footer page number on every page (except the title page)."""
    canvas.saveState()
    if doc.page > 1:
        # Header band
        canvas.setFillColor(BRAND)
        canvas.rect(0, A4[1] - 14 * mm, A4[0], 14 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15 * mm, A4[1] - 9 * mm,
                          "WFM x Finance Integration  -  Implementation Report")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(A4[0] - 15 * mm, A4[1] - 9 * mm,
                               datetime.now().strftime("%Y-%m-%d"))
    # Footer
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(A4[0] / 2, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_story():
    story = []

    # ---------------------- Cover ---------------------- #
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("WFM &times; Finance Integration", S["title"]))
    story.append(Paragraph("Implementation Report", S["subtitle"]))
    story.append(Paragraph(
        "FastAPI Backend &middot; Agent-Level Financial Model &middot; v0.1",
        S["subtitle_italic"]))
    story.append(Spacer(1, 1.2 * cm))

    story.append(styled_table([
        ["Field", "Value"],
        ["Source design", "WFM_Finance_Integration_Design.pdf v0.1"],
        ["Stack", "FastAPI 0.115 / Python 3.11 / SQLAlchemy 2.0 / Pydantic 2.9"],
        ["Storage", "SQLite (local) - swap to Postgres via DATABASE_URL"],
        ["Tests", "26 / 26 passing"],
        ["HTTP routes", "33 endpoints"],
        ["Frontend", "Java compatible via CORS + OpenAPI client gen"],
        ["Data source", "Agent_Breakdown_140426.csv (streaming ingest)"],
        ["Report generated", datetime.now().strftime("%Y-%m-%d %H:%M")],
    ], col_widths=[5 * cm, 11 * cm]))
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        "Every section of the source design document is mapped to a concrete module, "
        "endpoint, and test case in this implementation. The full coverage matrix is on "
        "the last page.", S["callout"]))
    story.append(PageBreak())

    # ---------------------- 1. Executive Summary ---------------------- #
    story.append(Paragraph("1. Executive Summary", S["h1"]))
    story.append(Paragraph(
        "A stateless FastAPI service that consumes the WFM hourly breakdown and "
        "produces a per-agent financial breakdown of the same period. It owns the "
        "formulas; it never owns hours (WFM does) or rates (HR/Contracts does). "
        "The Billing Engine is a pure function over fully-hydrated inputs, which is "
        "the property that makes it testable, reproducible, and replayable for audit.",
        S["body"]))
    story.append(Paragraph("Three transport paths cover every realistic ingest mode:", S["body"]))
    story.append(styled_table([
        ["Path", "Driven by", "Use case"],
        ["POST /finance/breakdown", "WFM cron at end-of-shift",
         "Push model - the canonical section 7.1 contract"],
        ["POST /ingest/csv/*", "Java frontend or scheduled batch",
         "Bulk pull from Agent_Breakdown_140426.csv"],
        ["GET /ingest/csv/stream", "Java frontend EventSource",
         "Live progress feed via Server-Sent Events"],
    ], col_widths=[5 * cm, 5 * cm, 6 * cm]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Java-frontend compatibility comes from three things: (1) CORS allowlist "
        "pre-configured for typical JVM dev ports, (2) snake_case JSON matching the "
        "PDF contract verbatim, (3) an auto-generated OpenAPI 3 spec at /openapi.json "
        "that the openapi-generator CLI converts to typed Java DTOs.", S["body"]))

    # ---------------------- 2. Architecture ---------------------- #
    story.append(Paragraph("2. Architecture (PDF Section 3)", S["h1"]))
    story.append(Paragraph(
        "Five components and three data stores; one deterministic chain.", S["body"]))
    story.append(code(
        "WFM hourly breakdown  -->  Leave Ledger lookup  -->  Rate Card lookup\n"
        "                      -->  Billing Engine  -->  Per-agent financial record\n"
        "                                              |\n"
        "                                              +--> AuditLog (hash + provenance)\n"
        "                                              +--> Reconciliation queue"))
    story.append(styled_table([
        ["Component", "Owner", "Module"],
        ["WFM Aggregator", "Operations",
         "services/wfm_aggregator.py + services/csv_ingest.py"],
        ["Leave Ledger", "HR",
         "services/leave_service.py"],
        ["Rate Card Service", "HR / Contracts",
         "services/rate_card_service.py"],
        ["Billing Engine", "Finance",
         "services/billing_engine.py (pure)"],
        ["Reconciliation Service", "Finance + Operations",
         "services/reconciliation_service.py"],
    ], col_widths=[4.5 * cm, 3.5 * cm, 8 * cm]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "The Billing Engine never queries upstream systems mid-computation. It "
        "receives a fully hydrated <i>HourlyInputs + AgentRateInputs + LeaveResolution</i> "
        "and returns a deterministic <i>BillingResult</i>. The orchestrator "
        "<font name='Courier'>services/finance_service.py</font> is the only module that "
        "touches multiple repositories at once.", S["body"]))

    story.append(PageBreak())

    # ---------------------- 3. Seven-Step Pipeline ---------------------- #
    story.append(Paragraph("3. The Seven-Step Pipeline (PDF Section 5.1)", S["h1"]))
    story.append(styled_table([
        ["Step", "Operation", "Function"],
        ["1", "Classify worked hours -> regular / OT / night / holiday",
         "step1_classify_worked_hours"],
        ["2", "Resolve leave consumption (three policies)",
         "leave_service.resolve"],
        ["3", "Apply rate multipliers (holiday + OT non-stacking by default, configurable)",
         "step3_apply_rate_multipliers"],
        ["4", "Sum and accrue -> daily_gross",
         "step4_sum_and_accrue"],
        ["5", "Roll up to monthly window",
         "finance_service._month_to_date_gross"],
        ["6", "Apply min/max -> delta_reason + HR/Ops alerts",
         "step6_apply_min_max"],
        ["7", "Persist with content_hash + provenance + parent_id chain",
         "finance_service.process_breakdown"],
    ], col_widths=[1.2 * cm, 8.3 * cm, 6.5 * cm]))

    story.append(Paragraph("3.1 Worked example (PDF Section 5.2)", S["h2"]))
    story.append(Paragraph(
        "Encoded as a golden test (<font name='Courier'>"
        "tests/test_billing_engine.py::test_section_5_2_worked_example_golden</font>).",
        S["body"]))
    story.append(code(
        "regular_pay    = 168 x INR 250            = INR 42,000\n"
        "overtime_pay   = 12  x INR 250 x 1.5      = INR  4,500\n"
        "holiday_pay    =  8  x INR 250 x 2.0      = INR  4,000\n"
        "night_premium  = 20  x INR 250 x 0.10     = INR    500\n"
        "                                            -----------\n"
        "                monthly_gross             = INR 51,000\n"
        "\n"
        "min/max check  : INR 35,000 < INR 51,000 < INR 70,000  -> pass through\n"
        "                Final monthly_pay         = INR 51,000"))

    story.append(Paragraph("3.2 Live verification", S["h2"]))
    story.append(Paragraph(
        "Smoke test against the running server using the worked-example agent:",
        S["body"]))
    story.append(code(
        'curl -X POST http://localhost:8000/finance/breakdown -H "Content-Type: application/json" \\\n'
        '  -d \'{"agent_id":"WORKED_EXAMPLE","date":"2026-04-14",\n'
        '       "productive_minutes":480,"available_minutes":0,"break_minutes":0,\n'
        '       "training_minutes":0,"scheduled_minutes":480,"worked_minutes":510,\n'
        '       "overtime_minutes":30,"is_holiday":false,"night_minutes":60}\'\n'
        '\n'
        '-> 200 OK\n'
        '   daily_gross    : 2212.5000\n'
        '   regular_pay    : 2000.0000\n'
        '   overtime_pay   :  187.5000\n'
        '   night_premium  :   25.0000\n'
        '   content_hash   : 786292e467efabb7...'))

    story.append(PageBreak())

    # ---------------------- 4. Leave Consumption ---------------------- #
    story.append(Paragraph("4. Leave Consumption - The Critical Edge Case (PDF Section 6)",
                           S["h1"]))
    story.append(Paragraph(
        "Three explicit policies on each LeaveLedger row, set per agent at contract time. "
        "All three are implemented in <font name='Courier'>services/leave_service.py</font> "
        "and individually tested.", S["body"]))
    story.append(styled_table([
        ["Policy", "Behaviour", "HTTP outcome"],
        ["BLOCK (6.1)",
         "Absence rejected; HR override required.",
         "409 Conflict + BLOCK_POLICY_TRIGGERED"],
        ["UNPAID_AUTO (6.2)",
         "Recorded as LWP at zero rate; daily HR alert.",
         "200 + billing_status = UNPAID_LWP"],
        ["MANAGER_APPROVAL (6.3)",
         "Queued as PendingApproval; billing not finalised.",
         "200 + billing_status = PENDING_APPROVAL"],
    ], col_widths=[3.8 * cm, 7.7 * cm, 5 * cm]))

    story.append(Paragraph("4.1 Manager decision flow (PDF Section 6.3)", S["h2"]))
    story.append(bullet("POST <font name='Courier'>/reconciliation/pending-approvals/{id}/decision</font> with body "
                        "<font name='Courier'>{manager_id, decision: 'APPROVE'|'DENY', note}</font>."))
    story.append(bullet("APPROVE - treated as paid exception; ledger gets +1 approved and +1 consumed."))
    story.append(bullet("DENY - reverts to unpaid."))
    story.append(bullet("Section 6.3 month-close gate: while any PENDING_APPROVAL exists in the month, "
                        "<font name='Courier'>monthly_rollup</font> appends a blocking alert and "
                        "<font name='Courier'>days_counted</font> excludes those rows."))

    story.append(Paragraph("4.2 Daily Reconciliation (PDF Section 6.4)", S["h2"]))
    story.append(styled_table([
        ["Check", "What it does", "Threshold"],
        ["Coverage",
         "scheduled_minutes vs worked_minutes per agent",
         "10% variance (configurable)"],
        ["Leave-balance integrity",
         "WFM absences vs Leave Ledger consumed (PDF Section 10)",
         "0.5 leave-day drift"],
        ["Preview vs actual",
         "Preview OT cost vs actual recorded OT cost (PDF Section 10)",
         "5% drift"],
        ["Pending close block",
         "Surfaces any PENDING_APPROVAL rows for the month",
         "BLOCK severity"],
    ], col_widths=[3.5 * cm, 8.5 * cm, 4.5 * cm]))

    # ---------------------- 5. The Contract ---------------------- #
    story.append(Paragraph("5. The WFM <-> Finance Contract (PDF Section 7)", S["h1"]))
    story.append(styled_table([
        ["Endpoint", "Section", "Notes"],
        ["POST /finance/breakdown",
         "7.1 + 7.2",
         "WFM publishes daily-finalised event; Finance returns cost preview."],
        ["POST /finance/breakdown/from-wfm-raw",
         "7.1 + 11",
         "Accepts a raw {status: minutes} map; aggregator + pipeline run in one call."],
        ["POST /finance/preview",
         "7.3",
         "SYNCHRONOUS OT preview - estimated_additional_cost, cap_breach, approval_recommendation."],
        ["GET  /finance/breakdown/{agent}/{date}", "-", "Read-back for the Java dashboard."],
        ["GET  /finance/breakdown/{agent}?start=&end=", "-", "Date-range read."],
        ["GET  /finance/monthly/{agent}/{year}/{month}",
         "5.1 step 5 + 6",
         "Month-close rollup with min/max applied to ACTUAL monthly_gross."],
    ], col_widths=[6.5 * cm, 2 * cm, 8 * cm]))

    story.append(PageBreak())

    # ---------------------- 6. CSV Streaming Ingest ---------------------- #
    story.append(Paragraph("6. Streaming CSV Ingest", S["h1"]))
    story.append(Paragraph(
        "WFM data lives in <font name='Courier'>Agent_Breakdown_140426.csv</font> and is "
        "consumed row-by-row so memory stays bounded for arbitrarily large extracts. "
        "Each row is bucketised per (agent_id, local_date), routed through the Section 11 "
        "Status -> Pay Category mapping, then handed to the same seven-step Billing Engine.",
        S["body"]))
    story.append(code(
        "CSV row\n"
        "  --> normalise headers / parse local interval start\n"
        "  --> accumulate per (agent_id, work_date)\n"
        "  --> wfm_aggregator.aggregate_status_map (Section 11)\n"
        "  --> finance_service.process_breakdown (Section 5.1 - all 7 steps)\n"
        "  --> FinancialBreakdown row + content_hash + provenance (Section 8)"))

    story.append(Paragraph("6.1 Driving the ingest", S["h2"]))
    story.append(styled_table([
        ["Mode", "Endpoint / Command"],
        ["Server-side file by path", "POST /ingest/csv/path?path=..."],
        ["Multipart upload from frontend", "POST /ingest/csv/upload  (form field 'file')"],
        ["Live progress feed (SSE)", "GET  /ingest/csv/stream"],
        ["Dry-run preview", "GET  /ingest/csv/preview?limit=20"],
        ["CLI / cron batch", "python -m app.cli ingest [--path PATH] [--auto-create]"],
    ], col_widths=[6 * cm, 10.5 * cm]))

    story.append(Paragraph("6.2 Column mapping", S["h2"]))
    story.append(styled_table([
        ["CSV header", "Used as"],
        ["Agent Id", "agent_id"],
        ["Status", "WFM status (Section 11 routing)"],
        ["Vendor Site", "site - drives per-site holiday calendar"],
        ["local_interval_sta (truncated in source)", "local date for the agent-day bucket"],
        ["Local Start Time", "activity start - night-window check"],
        ["time_in_interval_m", "minutes in this status / interval"],
    ], col_widths=[7 * cm, 9.5 * cm]))

    story.append(Paragraph("6.3 Smoke test against the real CSV", S["h2"]))
    story.append(code(
        "$ python -m app.cli ingest --auto-create\n"
        "\n"
        "[OK] 61581666459416 2026-04-12 site=Teleperformance-Dublin  rows= 66 gross=93.80\n"
        "[OK] 61581666459416 2026-04-13 site=Teleperformance-Dublin  rows= 64 gross=135.27\n"
        "[OK] 61581666459416 2026-04-14 site=Teleperformance-Dublin  rows= 18 gross=25.29\n"
        "...\n"
        "Summary:\n"
        "                    OK: 42\n"
        "               BLOCKED: 0\n"
        " SKIPPED_UNKNOWN_AGENT: 0\n"
        "                 ERROR: 0\n"
        "\n"
        "Aggregate parser sees:\n"
        "  unique agents : 20\n"
        "  unique days   : 2026-04-12 / 2026-04-13 / 2026-04-14\n"
        "  total minutes : 11,728.7\n"
        "  night minutes : 1,028.5"))

    story.append(PageBreak())

    # ---------------------- 7. Auditability ---------------------- #
    story.append(Paragraph("7. Auditability & Compliance (PDF Section 8)", S["h1"]))
    story.append(Paragraph(
        "Every FinancialBreakdown row carries:", S["body"]))
    story.append(bullet("<b>provenance</b> - full input snapshot (hours + rates + leave resolution + step1 buckets + settings)."))
    story.append(bullet("<b>content_hash</b> - SHA-256 of canonicalised provenance + components."))
    story.append(bullet("<b>parent_id</b> - when a correction lands (WFM re-publishes worked_minutes), the new "
                        "record points to the original. The original is preserved - mitigates Section 10 "
                        "<i>'Backfill of corrections poisons month-end'</i>."))
    story.append(Paragraph(
        "In addition, the AuditLog captures BILLING_COMPUTED, BILLING_BLOCKED, "
        "MANAGER_DECISION, and LEAVE_BALANCE_ADJUSTED events with actor + timestamp.",
        S["body"]))

    # ---------------------- 8. Risks ---------------------- #
    story.append(Paragraph("8. Risk Mitigations Implemented (PDF Section 10)", S["h1"]))
    story.append(styled_table([
        ["Risk", "Mitigation", "Where"],
        ["Stale rate cards produce wrong cost previews",
         "version_id + 24h TTL flag in preview response",
         "rate_card_service.is_stale"],
        ["WFM and Leave Ledger drift apart",
         "Daily reconciliation; alert if drift > 0.5 day",
         "reconciliation_service._leave_integrity_check"],
        ["Holiday calendar mismatch across regions",
         "Per-site calendar; multi-site agents resolve by primary_site",
         "HolidayCalendar + finance_service._resolve_holiday"],
        ["Overtime gaming (clock-in early/late)",
         "Explicit OT requires WFM-approved overtime_minutes; un-approved -> regular rate",
         "billing_engine.step1_classify_worked_hours"],
        ["Min-pay floor activations hidden from HR",
         "Every floor activation emits a MIN_FLOOR_APPLIED alert",
         "billing_engine.step6_apply_min_max"],
        ["Backfill of corrections poisons month-end",
         "New record + parent_id; original preserved",
         "finance_service.process_breakdown"],
    ], col_widths=[4.8 * cm, 6 * cm, 5.7 * cm]))

    # ---------------------- 9. Tests ---------------------- #
    story.append(Paragraph("9. Test Results", S["h1"]))
    story.append(code("$ python -m pytest -q\n.......................... 26 passed in 0.19s"))
    story.append(styled_table([
        ["Suite", "Coverage"],
        ["test_billing_engine.py",
         "Steps 1, 3, 6 individually + full compute + Section 5.2 golden case"],
        ["test_leave_policies.py",
         "BLOCK (6.1), UNPAID_AUTO (6.2), MANAGER_APPROVAL (6.3) + decide_pending"],
        ["test_reconciliation.py",
         "Coverage variance threshold + pending-approval blocks month-close"],
        ["test_status_mapping.py",
         "Section 11 appendix - productive / paid_idle / shrinkage / training / unmapped"],
        ["test_csv_ingest.py",
         "Per-status aggregation + multi-day split + night-window + agent filter + "
         "blank-row handling + BOM tolerance"],
    ], col_widths=[4.5 * cm, 12 * cm]))

    # ---------------------- 10. How to run ---------------------- #
    story.append(Paragraph("10. How to Run & Test", S["h1"]))
    story.append(Paragraph("Setup", S["h3"]))
    story.append(code(
        "cd c:\\mudrik\\mvp_ireland\\finance\\backend\n"
        "pip install -r requirements.txt\n"
        "python seed_data.py      # loads Section 5.2 worked-example + CSV sample agents\n"
        "python run.py            # starts uvicorn on :8000"))
    story.append(Paragraph("Quick sanity loop", S["h3"]))
    story.append(code(
        "python -m pytest -q                       # 1. unit + integration tests\n"
        "python seed_data.py                       # 2. seed the DB\n"
        "python -m app.cli ingest --auto-create    # 3. real CSV through end-to-end\n"
        "python run.py                             # 4. open http://localhost:8000/docs"))
    story.append(Paragraph("Where to point your browser", S["h3"]))
    story.append(styled_table([
        ["URL", "What it is"],
        ["http://localhost:8000/docs", "Swagger UI - click 'Try it out' on any endpoint"],
        ["http://localhost:8000/redoc", "ReDoc - read-only API browser"],
        ["http://localhost:8000/openapi.json", "OpenAPI 3 spec - feed to openapi-generator"],
        ["http://localhost:8000/health", "Liveness JSON"],
    ], col_widths=[7 * cm, 9.5 * cm]))
    story.append(Paragraph(
        "Note: <font name='Courier'>0.0.0.0</font> in the uvicorn output is a "
        "<i>bind</i> address (listen on all interfaces); browse to "
        "<font name='Courier'>localhost</font> or <font name='Courier'>127.0.0.1</font>.",
        S["callout"]))

    story.append(PageBreak())

    # ---------------------- 11. PDF coverage matrix ---------------------- #
    story.append(Paragraph("11. Design Doc Coverage Matrix", S["h1"]))
    story.append(Paragraph(
        "Every section of WFM_Finance_Integration_Design.pdf v0.1 is mapped to a "
        "concrete artefact in this implementation.", S["body"]))
    story.append(styled_table([
        ["PDF Section", "Title", "Implemented in"],
        ["1", "Problem Statement",
         "Architecture addresses all 3 failure modes - see Section 2 above."],
        ["2.1", "Goals - In Scope",
         "All 5 in-scope items implemented (per-agent billing, min/max, leave, preview, "
         "daily/weekly/monthly cycles)."],
        ["2.2", "Out of Scope (v1)",
         "Explicitly NOT implemented; documented in README."],
        ["3.1", "Component View",
         "5 components mapped in services/ (see Section 2 of this report)."],
        ["3.2", "Data Flow",
         "Deterministic chain in finance_service.process_breakdown."],
        ["4.1", "Agent Master",
         "models.Agent + routes /agents (CRUD)."],
        ["4.2", "Leave Ledger",
         "models.LeaveLedger + routes /leaves (CRUD + adjust)."],
        ["4.3", "Hourly Breakdown Input",
         "schemas.HourlyBreakdownIn - matches PDF field set 1:1."],
        ["5.1", "Seven-Step Pipeline",
         "services/billing_engine.py - all 7 steps as individual functions."],
        ["5.2", "Worked Example",
         "Golden test test_section_5_2_worked_example_golden + live curl smoke."],
        ["6.1", "Policy: BLOCK",
         "leave_service - returns 409 BLOCK_POLICY_TRIGGERED."],
        ["6.2", "Policy: UNPAID_AUTO",
         "leave_service - billing_status = UNPAID_LWP + HR alert."],
        ["6.3", "Policy: MANAGER_APPROVAL",
         "PendingApproval queue + /reconciliation/pending-approvals/{id}/decision."],
        ["6.4", "Daily Reconciliation",
         "3 checks in reconciliation_service.run + pending close block."],
        ["7.1", "What WFM publishes",
         "POST /finance/breakdown - body matches PDF JSON shape."],
        ["7.2", "What Finance publishes back",
         "schemas.BillingResponse - matches PDF response shape."],
        ["7.3", "Operations cost-preview endpoint",
         "POST /finance/preview - synchronous, returns approval_recommendation."],
        ["8", "Auditability & Compliance",
         "content_hash on every row + parent_id chain + AuditLog table."],
        ["9", "Rollout Plan",
         "Phases 0-4 mapped in README; engine isolated for Phase 0 unit tests."],
        ["10", "Risks & Mitigations",
         "All 6 risks have explicit mitigations - see Section 8 above."],
        ["11", "Appendix: Status -> Pay Category",
         "utils/status_mapping.py + GET /status-mapping - all 8 statuses."],
    ], col_widths=[1.7 * cm, 5 * cm, 9.8 * cm]))

    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        "Document generated by <font name='Courier'>backend/generate_report.py</font>. "
        "Re-run after each significant change to keep the audit trail current.",
        S["callout"]))

    return story


def main():
    out_path = Path(__file__).resolve().parent.parent / "WFM_Finance_Implementation_Report.pdf"
    doc = BaseDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title="WFM x Finance Integration - Implementation Report",
        author="Finance Platform",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="body",
    )
    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=on_page)])
    doc.build(build_story())
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
