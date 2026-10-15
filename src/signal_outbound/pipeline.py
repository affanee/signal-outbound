"""Signals in, sequencer-ready rows out. Every drop is counted and explained.

    load -> classify (drop noise) -> age filter -> one signal per account
    -> cooldown (don't hit the same account twice in N days)
    -> pick the right person -> draft -> fact guard -> export
"""

from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .guard import check
from .signals import classify, load_signals, strength

# Who to write to, by signal type. First match in the account wins.
PERSONA = {
    "funding":       ["chief revenue officer", "vp sales", "head of sales", "founder"],
    "revops_hire":   ["revenue operations", "sales operations", "chief revenue officer", "vp sales"],
    "sales_hiring":  ["head of sales", "vp sales", "sales manager", "chief revenue officer"],
    "new_exec":      ["chief revenue officer", "vp sales", "head of sales"],
    "tech_adoption": ["sales operations", "revenue operations", "sales manager", "head of sales"],
}


@dataclass
class Run:
    today: date
    counts: dict = field(default_factory=lambda: {
        "signals": 0, "noise": 0, "stale": 0, "weaker_same_account": 0,
        "cooldown": 0, "no_contact": 0, "drafted": 0, "rejected": 0, "exported": 0,
    })
    dropped: list = field(default_factory=list)     # (signal_id, account, reason)
    exported: list = field(default_factory=list)    # dict rows
    rejected: list = field(default_factory=list)    # dict rows


def _state(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE IF NOT EXISTS touches (account TEXT, signal_id TEXT,"
                 " touched_on TEXT, PRIMARY KEY (account, signal_id))")
    return conn


def _last_touch(conn, account: str) -> date | None:
    row = conn.execute("SELECT MAX(touched_on) FROM touches WHERE account = ?",
                       (account,)).fetchone()
    return date.fromisoformat(row[0]) if row and row[0] else None


def _pick_contact(contacts: list[dict], account: str, sig_type: str) -> dict | None:
    pool = [c for c in contacts if c["account"].lower() == account]
    for wanted in PERSONA.get(sig_type, []):
        for c in pool:
            if wanted in c["title"].lower():
                return c
    return None


def run(signals_path, contacts_path, writer, today: date, *, max_age: int = 30,
        cooldown_days: int = 21, state_path="data/state.db", dry_run=False) -> Run:
    r = Run(today=today)
    sigs = load_signals(signals_path)
    contacts = json.loads(Path(contacts_path).read_text(encoding="utf-8"))
    conn = _state(state_path)
    r.counts["signals"] = len(sigs)

    # 1-2. classify and age-filter
    live = []
    for s in sigs:
        sig_type, why = classify(s)
        if not sig_type:
            r.counts["noise"] += 1
            r.dropped.append((s.id, s.account, f"noise: {why}"))
            continue
        age = (today - s.date).days
        st = strength(sig_type, age, max_age)
        if st <= 0:
            r.counts["stale"] += 1
            r.dropped.append((s.id, s.account, f"stale: {age} days old (limit {max_age})"))
            continue
        live.append((st, s, sig_type))

    # 3. strongest signal per account
    best: dict = {}
    for st, s, t in sorted(live, key=lambda x: -x[0]):
        if s.account in best:
            r.counts["weaker_same_account"] += 1
            r.dropped.append((s.id, s.account,
                              f"weaker than {best[s.account][1].id} for the same account"))
            continue
        best[s.account] = (st, s, t)

    for account, (st, s, sig_type) in sorted(best.items(), key=lambda kv: -kv[1][0]):
        # 4. cooldown
        last = _last_touch(conn, account)
        if last and (today - last).days < cooldown_days:
            r.counts["cooldown"] += 1
            r.dropped.append((s.id, account,
                              f"cooldown: touched {(today - last).days} days ago (min {cooldown_days})"))
            continue

        # 5. persona
        c = _pick_contact(contacts, account, sig_type)
        if not c:
            r.counts["no_contact"] += 1
            r.dropped.append((s.id, account, f"no contact matching a {sig_type} persona"))
            continue

        # 6. draft + guard
        line = writer.draft(s, sig_type, c)
        r.counts["drafted"] += 1
        evidence = " | ".join([s.text, c["first_name"], c["last_name"], c["title"], s.company])
        v = check(line, evidence, s.text)
        base = {"account": account, "email": c["email"], "first_name": c["first_name"],
                "last_name": c["last_name"], "company": s.company, "title": c["title"],
                "first_line": line, "signal_type": sig_type, "signal_id": s.id,
                "signal_strength": st, "signal_text": s.text}
        if not v.ok:
            r.counts["rejected"] += 1
            r.rejected.append({**base, "why_rejected": "; ".join(v.reasons)})
            continue

        r.counts["exported"] += 1
        r.exported.append(base)
        if not dry_run:
            conn.execute("INSERT OR IGNORE INTO touches VALUES (?,?,?)",
                         (account, s.id, today.isoformat()))
    conn.commit()
    conn.close()
    return r


def write_outputs(r: Run, out_dir="out") -> tuple[Path, Path]:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    seq = out / "sequencer_import.csv"
    rej = out / "rejected.csv"
    # Column names match what Smartlead / Instantly / Apollo accept on CSV import;
    # first_line is mapped to a custom variable like {{first_line}} in the template.
    seq_cols = ["email", "first_name", "last_name", "company", "title", "first_line",
                "signal_type", "signal_id"]
    with seq.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=seq_cols, extrasaction="ignore")
        w.writeheader(); w.writerows(r.exported)
    with rej.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=seq_cols + ["why_rejected", "signal_text"],
                           extrasaction="ignore")
        w.writeheader(); w.writerows(r.rejected)
    return seq, rej
