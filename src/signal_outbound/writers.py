"""Write the first line of an outreach email from a signal.

Two writers live here, and the difference between them is the whole lesson.

TemplateWriter  - the default. Pulls facts out of the signal text verbatim
                  (the amount, the round, the role title) and slots them into
                  a sentence. It can only ever say what the signal says.

NaiveWriter     - a SIMULATION of what a careless AI writer does: it takes
                  the same signal and "improves" it — rounds numbers up,
                  names an investor that sounds right, adds a headcount.
                  It exists only so the demo can show the fact guard catching
                  it. Its output is never exported.

A real LLM writer would plug in with the same draft(signal, contact) shape,
and its output would go through the same guard.
"""

from __future__ import annotations

import hashlib
import re

from .guard import SERIES_RE
from .signals import EXEC_TITLES, REVOPS_TITLES, SALES_TITLES, Signal

AMOUNT_RE = re.compile(r"\$\d[\d,.]*\s?[MBK]?\b", re.I)
# "is hiring a Revenue Operations Manager in ..." -> "Revenue Operations Manager"
# Taken from the sentence structure, not keyword search, because a keyword
# search matched the company name "Cadence RevOps" and produced "hiring a RevOps".
ROLE_RE = re.compile(
    r"hiring (?:a|an|two|three|four|several|\d+)?\s*([A-Z][A-Za-z/&\- ]+?)(?: roles?)?\s+(?:in|to|for|at)\b")
TOOLS = ["Salesforce Sales Cloud", "Salesforce", "HubSpot Sales Hub", "HubSpot",
         "Outreach", "Salesloft", "Gong", "Clay", "Apollo"]

WHY = {
    "funding": "that's usually the point where the revenue team outgrows its first set of tools",
    "revops_hire": "that hire usually means the current setup is starting to creak",
    "sales_hiring": "more reps usually means routing and territories get tested fast",
    # This line used to say "in their first 90 days". The fact guard rejected it:
    # 90 is a number that is not in the evidence. It was right to — the guard
    # cannot tell a sender's rule of thumb from a claim about the prospect, and
    # it should not have to. Keep the house copy free of figures.
    "new_exec": "new revenue leaders tend to rebuild the pipeline view early on",
    "tech_adoption": "the first few months after a CRM move are when the data gets decided",
}


def _first(pattern: re.Pattern, text: str) -> str:
    m = pattern.search(text)
    return m.group(0) if m else ""


class TemplateWriter:
    name = "template"

    def draft(self, sig: Signal, sig_type: str, contact: dict) -> str:
        first = contact["first_name"]
        company = sig.company
        t = sig.text
        why = WHY.get(sig_type, "")

        if sig_type == "funding":
            amount, series = _first(AMOUNT_RE, t), _first(SERIES_RE, t)
            round_ = " ".join(x for x in (amount, series) if x) or "new round"
            return f"Congrats on the {round_}, {first} — {why}."
        if sig_type == "revops_hire":
            m = ROLE_RE.search(t)
            role = m.group(1).strip() if m else _first(REVOPS_TITLES, t)
            return f"{first}, noticed {company} is hiring a {role} — {why}."
        if sig_type == "sales_hiring":
            m = ROLE_RE.search(t)
            role = m.group(1).strip() if m else _first(SALES_TITLES, t)
            return f"{first}, saw {company} is adding {role} roles — {why}."
        if sig_type == "new_exec":
            title = _first(EXEC_TITLES, t)
            return f"{first}, congrats on the {title} role at {company} — {why}."
        if sig_type == "tech_adoption":
            tool = next((x for x in TOOLS if x in t), "")
            return f"{first}, noticed {company} recently moved onto {tool} — {why}."
        return f"{first}, saw the recent news at {company}."


class NaiveWriter(TemplateWriter):
    """SIMULATED careless writer. Demonstration only; never exported."""

    name = "naive (simulated)"

    def draft(self, sig: Signal, sig_type: str, contact: dict) -> str:
        line = super().draft(sig, sig_type, contact)
        # Deterministic "creativity", so the demo gives the same result every run.
        roll = int(hashlib.sha256(sig.id.encode()).hexdigest(), 16) % 4
        if roll == 0:
            # round the number up, the way a model "remembers" it
            line = re.sub(r"\$(\d+)", lambda m: f"${int(m.group(1)) + 8}", line)
            line = line.replace("Series A", "Series B").replace("Series B", "Series C", 1) \
                if "Series" in line else line
        elif roll == 1:
            line = line.replace(" — ", ", and with Sequoia now on the cap table — ", 1)
        elif roll == 2:
            line = line.replace(" — ", " (and at 400+ people now) — ", 1)
        return line
