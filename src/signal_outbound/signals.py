"""Load signals and decide which ones are worth acting on.

A signal is something that happened at an account: a job post, a funding
round, a new executive, a tool they started using. Most signals are noise.
This module keeps the ones that suggest the account is building or fixing
its revenue engine right now, and scores how strong each one is.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# type -> base strength. A funded company with a new CRO is a much better
# reason to reach out than a company that published a blog post.
BASE_STRENGTH = {
    "new_exec": 90,
    "revops_hire": 85,
    "funding": 75,
    "tech_adoption": 60,
    "sales_hiring": 50,
}

# Job titles that mean "we are building revenue operations right now".
REVOPS_TITLES = re.compile(
    r"\b(rev\s?ops|revenue operations|sales operations|gtm (engineer|operations|systems)|"
    r"go[- ]to[- ]market (engineer|operations)|crm (admin|manager))\b",
    re.I,
)
SALES_TITLES = re.compile(r"\b(account executive|sdr|bdr|sales development|sales manager)\b", re.I)
EXEC_TITLES = re.compile(r"\b(chief revenue officer|cro|vp (of )?sales|head of sales|vp revenue)\b", re.I)


@dataclass
class Signal:
    id: str
    account: str
    company: str
    kind: str          # job_post | funding | exec_change | tech_change
    date: date
    text: str          # the source text, verbatim. The only evidence a draft may use.
    source: str

    @property
    def age_days(self) -> int:
        return (date.today() - self.date).days


def load_signals(path: str | Path) -> list[Signal]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for r in raw:
        out.append(Signal(
            id=r["id"], account=r["account"].lower().strip(), company=r["company"],
            kind=r["kind"], date=date.fromisoformat(r["date"]), text=r["text"],
            source=r.get("source", ""),
        ))
    return out


def classify(sig: Signal) -> tuple[str, str]:
    """Return (signal_type, reason) or ("", reason) if the signal is noise."""
    t = sig.text
    if sig.kind == "exec_change":
        if EXEC_TITLES.search(t):
            return "new_exec", "new revenue leader"
        return "", "executive change, but not a revenue role"
    if sig.kind == "funding":
        return "funding", "new funding round"
    if sig.kind == "tech_change":
        return "tech_adoption", "adopted a relevant tool"
    if sig.kind == "job_post":
        if REVOPS_TITLES.search(t):
            return "revops_hire", "hiring for revenue operations"
        if SALES_TITLES.search(t):
            return "sales_hiring", "hiring salespeople"
        return "", "job post for a role outside the revenue team"
    return "", f"unknown signal kind '{sig.kind}'"


def strength(sig_type: str, age_days: int, max_age: int) -> float:
    """Base strength, decaying linearly to zero at max_age days."""
    if age_days < 0 or age_days > max_age:
        return 0.0
    return round(BASE_STRENGTH.get(sig_type, 0) * (1 - age_days / max_age), 1)
