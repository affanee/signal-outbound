import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from signal_outbound.pipeline import run
from signal_outbound.signals import classify, load_signals
from signal_outbound.writers import NaiveWriter, TemplateWriter

ROOT = Path(__file__).resolve().parents[1]
SIGS, CONTACTS = ROOT / "data" / "signals.json", ROOT / "data" / "contacts.json"
TODAY = date(2026, 9, 21)


def _run(tmp_path, writer=None, **kw):
    return run(SIGS, CONTACTS, writer or TemplateWriter(), TODAY,
               state_path=tmp_path / "s.db", **kw)


def test_template_writer_passes_its_own_guard(tmp_path):
    r = _run(tmp_path)
    assert r.counts["rejected"] == 0
    assert r.counts["exported"] == r.counts["drafted"] > 0

def test_second_run_same_day_sends_nothing(tmp_path):
    first = _run(tmp_path)
    second = _run(tmp_path)
    assert first.counts["exported"] > 0
    assert second.counts["exported"] == 0
    assert second.counts["cooldown"] == first.counts["exported"]

def test_cooldown_expires(tmp_path):
    _run(tmp_path)
    later = run(SIGS, CONTACTS, TemplateWriter(), date(2026, 10, 14),
                state_path=tmp_path / "s.db", max_age=60)
    assert later.counts["cooldown"] == 0

def test_dry_run_records_nothing(tmp_path):
    _run(tmp_path, dry_run=True)
    assert _run(tmp_path).counts["cooldown"] == 0

def test_naive_writer_gets_caught(tmp_path):
    r = _run(tmp_path, writer=NaiveWriter(), dry_run=True)
    assert r.counts["rejected"] >= 3

def test_one_signal_per_account(tmp_path):
    r = _run(tmp_path)
    accounts = [row["account"] for row in r.exported]
    assert len(accounts) == len(set(accounts))

def test_strongest_signal_wins(tmp_path):
    # Northwind has a funding round AND a RevOps hire; the hire is stronger.
    r = _run(tmp_path)
    nw = [row for row in r.exported if row["account"] == "northwind-signals.com"][0]
    assert nw["signal_type"] == "revops_hire"
    assert "revenue operations" in nw["title"].lower()

def test_noise_is_dropped():
    sigs = {s.id: s for s in load_signals(SIGS)}
    assert classify(sigs["s06"])[0] == ""   # frontend engineer
    assert classify(sigs["s07"])[0] == ""   # new CFO
    assert classify(sigs["s11"])[0] == "revops_hire"  # GTM engineer

def test_stale_signal_is_dropped(tmp_path):
    r = _run(tmp_path)
    assert any(d[0] == "s08" and d[2].startswith("stale") for d in r.dropped)

def test_company_name_is_not_mistaken_for_a_role(tmp_path):
    r = _run(tmp_path)
    row = [x for x in r.exported if x["account"] == "cadence-revops.com"][0]
    assert "hiring a Sales Operations Lead" in row["first_line"]
