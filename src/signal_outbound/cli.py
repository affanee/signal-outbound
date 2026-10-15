"""Command line entry point.

    python -m signal_outbound run --today 2026-09-21
    python -m signal_outbound run --writer naive --dry-run
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .pipeline import run, write_outputs
from .writers import NaiveWriter, TemplateWriter


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="signal-outbound")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="process signals into outreach rows")
    p.add_argument("--signals", default="data/signals.json")
    p.add_argument("--contacts", default="data/contacts.json")
    p.add_argument("--today", default=date.today().isoformat(),
                   help="pretend today is this date (YYYY-MM-DD); makes runs reproducible")
    p.add_argument("--writer", choices=["template", "naive"], default="template")
    p.add_argument("--cooldown", type=int, default=21)
    p.add_argument("--max-age", type=int, default=30)
    p.add_argument("--state", default="data/state.db")
    p.add_argument("--dry-run", action="store_true", help="don't record touches (no cooldown)")
    p.add_argument("--reset", action="store_true", help="forget all previous touches first")
    a = ap.parse_args(argv)

    if a.reset and Path(a.state).exists():
        Path(a.state).unlink()

    writer = NaiveWriter() if a.writer == "naive" else TemplateWriter()
    r = run(a.signals, a.contacts, writer, date.fromisoformat(a.today),
            max_age=a.max_age, cooldown_days=a.cooldown, state_path=a.state,
            dry_run=a.dry_run or a.writer == "naive")
    seq, rej = (None, None)
    if a.writer == "template":
        seq, rej = write_outputs(r)

    c = r.counts
    print(f"\nwriter: {writer.name}    today: {a.today}\n")
    print("FUNNEL")
    print(f"  {'signals in':<34}{c['signals']:>4}")
    print(f"  {'- noise (not a revenue signal)':<34}{c['noise']:>4}")
    print(f"  {'- stale (older than ' + str(a.max_age) + ' days)':<34}{c['stale']:>4}")
    print(f"  {'- weaker signal, same account':<34}{c['weaker_same_account']:>4}")
    print(f"  {'- on cooldown':<34}{c['cooldown']:>4}")
    print(f"  {'- no matching contact':<34}{c['no_contact']:>4}")
    print(f"  {'= drafted':<34}{c['drafted']:>4}")
    print(f"  {'- REJECTED by fact guard':<34}{c['rejected']:>4}")
    print(f"  {'= ready for the sequencer':<34}{c['exported']:>4}")

    if r.exported:
        print("\nREADY")
        for row in r.exported:
            print(f"  {row['email']}\n    \"{row['first_line']}\"")
    if r.rejected:
        print("\nREJECTED — these would have gone out with invented facts")
        for row in r.rejected:
            print(f"  {row['email']}\n    \"{row['first_line']}\"\n    ✗ {row['why_rejected']}")
    if seq:
        print(f"\nWrote {seq} and {rej}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
