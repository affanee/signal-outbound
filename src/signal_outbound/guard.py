"""The fact check. The reason this repo exists.

An outreach line is only allowed to contain facts that appear in the
evidence: the signal text, plus the contact's own record (their name,
title, company). Anything else is a claim nobody can back up.

We check the two kinds of fact that do real damage when invented:

  NUMBERS  - "$40M", "Series C", "12 open roles", "200%"
             Wrong numbers are the fastest way to look like a bot.
  NAMES    - capitalised proper nouns: people, companies, products, places.
             Congratulating someone on a hire that never happened ends the thread.

A line fails if it contains ANY number or name that is not in the evidence.
It also fails if it doesn't mention anything from the signal at all — a
line that could be sent to anyone is not signal-based outreach.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Capitalised words that are ordinary English at the start of a clause,
# or generic enough that they prove nothing. Extend as you find false alarms.
COMMON_CAPS = {
    "i", "hi", "hey", "hello", "congrats", "congratulations", "saw", "noticed",
    "just", "quick", "question", "curious", "looks", "looking", "love", "loved",
    "great", "nice", "big", "huge", "exciting", "happy", "thanks", "thank",
    "the", "a", "an", "your", "you", "we", "our", "it", "its", "that", "this",
    "with", "on", "in", "at", "for", "and", "but", "so", "if", "when", "as",
    "is", "are", "was", "be", "been", "how", "what", "why", "who", "would",
    "could", "should", "any", "most", "many", "some", "every", "each",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "q1", "q2", "q3", "q4",
    "ceo", "cro", "cto", "cfo", "vp", "revops", "gtm", "crm", "sdr", "bdr",
    "ae", "saas", "b2b", "ai", "api", "ops", "head", "director", "manager",
}

NUMBER_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s?(?:%|[kKmMbB]\b|million|billion)?")
SERIES_RE = re.compile(r"\bSeries\s+[A-H]\b")
# A run of capitalised words, e.g. "Sarah Chen", "Northwind Signals", "Salesforce".
PROPER_RE = re.compile(r"\b[A-Z][a-zA-Z0-9&'\-]*(?:\s+[A-Z][a-zA-Z0-9&'\-]*)*")
STOP = COMMON_CAPS | {"about", "from", "into", "their", "they", "them", "have",
                      "has", "had", "will", "just", "team", "role", "roles"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def _number_core(tok: str) -> str:
    """'$42M' -> '42', '1,200' -> '1200', '35%' -> '35'"""
    return re.sub(r"[^\d.]", "", tok).rstrip(".")


def extract_numbers(text: str) -> list[str]:
    out = []
    for m in NUMBER_RE.finditer(text):
        core = _number_core(m.group(0))
        if core:
            out.append(m.group(0).strip())
    return out


def extract_names(text: str) -> list[str]:
    names = []
    for m in SERIES_RE.finditer(text):
        names.append(m.group(0))
    for m in PROPER_RE.finditer(text):
        phrase = m.group(0).strip()
        words = [w for w in phrase.split() if w.lower().strip("'") not in COMMON_CAPS]
        if not words:
            continue
        cleaned = " ".join(words)
        if cleaned.lower().startswith("series "):
            continue
        names.append(cleaned)
    return names


@dataclass
class Verdict:
    ok: bool
    unsupported_numbers: list[str] = field(default_factory=list)
    unsupported_names: list[str] = field(default_factory=list)
    generic: bool = False

    @property
    def reasons(self) -> list[str]:
        r = []
        for n in self.unsupported_numbers:
            r.append(f"number '{n}' is not in the evidence")
        for n in self.unsupported_names:
            r.append(f"name '{n}' is not in the evidence")
        if self.generic:
            r.append("mentions nothing specific from the signal")
        return r


def check(line: str, evidence: str, signal_text: str) -> Verdict:
    """Is every number and name in `line` supported by `evidence`?"""
    ev = _norm(evidence)
    ev_numbers = {_number_core(n) for n in extract_numbers(evidence)}

    bad_numbers = [n for n in extract_numbers(line) if _number_core(n) not in ev_numbers]
    bad_names = [n for n in extract_names(line) if _norm(n) not in ev]

    # Specificity: at least one meaningful word from the signal must appear.
    sig_words = {w for w in re.findall(r"[a-z][a-z\-]{3,}", signal_text.lower()) if w not in STOP}
    line_words = set(re.findall(r"[a-z][a-z\-]{3,}", line.lower()))
    generic = not (sig_words & line_words)

    return Verdict(
        ok=not bad_numbers and not bad_names and not generic,
        unsupported_numbers=bad_numbers,
        unsupported_names=bad_names,
        generic=generic,
    )
