"""Batch CSV ingest CLI.

Examples:

    # Default — read settings.wfm_csv_path (../Agent_Breakdown_140426.csv)
    python -m app.cli ingest

    # Explicit path + restrict to one agent
    python -m app.cli ingest --path "C:/path/to/Agent_Breakdown_140426.csv" \\
        --only-agent-id 61581666459416

    # Auto-create placeholder agents for IDs not in Agent Master (sandbox use)
    python -m app.cli ingest --auto-create
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services import csv_pipeline


def cmd_ingest(args: argparse.Namespace) -> int:
    Base.metadata.create_all(bind=engine)
    csv_path = Path(args.path) if args.path else Path(settings.wfm_csv_path)
    if not csv_path.exists():
        print(f"[ingest] CSV not found at {csv_path}", file=sys.stderr)
        return 2

    db = SessionLocal()
    counters = {"OK": 0, "BLOCKED": 0, "SKIPPED_UNKNOWN_AGENT": 0, "ERROR": 0}
    try:
        for result in csv_pipeline.stream_ingest(
            db,
            csv_path,
            only_agent_id=args.only_agent_id,
            auto_create_unknown_agents=args.auto_create,
        ):
            counters[result.status] = counters.get(result.status, 0) + 1
            print(
                f"[{result.status:>22s}] {result.agent_id} {result.work_date} "
                f"site={result.site!s:24s} rows={result.row_count:3d} "
                f"gross={result.daily_gross!s:>10s} "
                f"alerts={len(result.alerts or [])}"
            )
    finally:
        db.close()

    print()
    print("Summary:")
    for k, v in counters.items():
        print(f"  {k:>22s}: {v}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.cli", description="WFM x Finance CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_p = sub.add_parser("ingest", help="Stream an Agent_Breakdown CSV into the Billing Engine.")
    ingest_p.add_argument("--path", help="CSV path (defaults to settings.wfm_csv_path).")
    ingest_p.add_argument("--only-agent-id", help="Restrict ingest to one agent.")
    ingest_p.add_argument(
        "--auto-create",
        action="store_true",
        help="Insert placeholder Agent Master rows for IDs missing from HR.",
    )
    ingest_p.set_defaults(func=cmd_ingest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
