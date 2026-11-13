"""Read deadline and requirements out of tender document text.

Principle: never guess silently. A value read with a strict pattern is "OK".
A value that needed OCR-style repair, disagrees with the API, or could not be
found is marked "CHECK" and carries the page number, so a human can verify it
in seconds.

Scanned PDFs: v1 does not run OCR itself. Feed this module the text from your
OCR engine of choice. A document with no text at all is flagged
NO_TEXT_LAYER instead of being silently skipped.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from .models import TZ, Finding, Notice

_OCR_FIX = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1"})

_KEYWORDS = r"(?:Angebotsfrist|Abgabefrist|Frist\s+zur\s+Abgabe|Ablauf\s+der\s+Angebotsfrist|tender\s+deadline|termin\s+sk[łl]adania\s+ofert)"


def _deadline_re(chars: str) -> re.Pattern:
    d = f"[{chars}]"
    return re.compile(
        rf"{_KEYWORDS}\D{{0,20}}({d}{{1,2}})\.({d}{{1,2}})\.({d}{{4}})"
        rf"(?:,?\s*(?:um\s*)?({d}{{1,2}})[:.]({d}{{2}}))?",
        re.IGNORECASE,
    )


_STRICT = _deadline_re("0-9")
_LOOSE = _deadline_re("0-9OoIl")

_NUMBER_WORDS = {"ein": 1, "eine": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5}
_REFS = re.compile(
    r"(?:mindestens|min\.)\s+(\d+|ein|eine|zwei|drei|vier|fünf)\s+Referenz",
    re.IGNORECASE,
)
_TURNOVER = re.compile(
    r"Jahresumsatz[^.\n]{0,60}?(\d{1,3}(?:\.\d{3})+|\d+)\s*(?:EUR|€)", re.IGNORECASE
)


def _to_dt(groups, repair: bool) -> Optional[datetime]:
    parts = [g for g in groups]
    if repair:
        parts = [g.translate(_OCR_FIX) if g else g for g in parts]
    try:
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        hour = int(parts[3]) if parts[3] else 0
        minute = int(parts[4]) if parts[4] else 0
        return datetime(year, month, day, hour, minute, tzinfo=TZ)
    except (ValueError, TypeError):
        return None


def split_pages(text: str) -> list[str]:
    """Pages are separated by form feed, as produced by pdftotext."""
    return text.split("\f")


def find_deadline(pages: list[str]) -> Optional[Finding]:
    for pattern, repair in ((_STRICT, False), (_LOOSE, True)):
        for number, page in enumerate(pages, start=1):
            m = pattern.search(page)
            if not m:
                continue
            dt = _to_dt(m.groups(), repair)
            if dt is None:
                return Finding("", number, "CHECK", "Datum nicht lesbar / unreadable date")
            return Finding(
                dt.strftime("%Y-%m-%dT%H:%M"),
                number,
                "CHECK" if repair else "OK",
                "OCR-like characters repaired" if repair else "",
            )
    return None


def find_requirements(pages: list[str]) -> list[Finding]:
    out: list[Finding] = []
    for number, page in enumerate(pages, start=1):
        m = _REFS.search(page)
        if m:
            raw = m.group(1).casefold()
            n = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
            out.append(Finding(f">={n} references", number))
        m = _TURNOVER.search(page)
        if m:
            out.append(Finding(f"annual turnover >= {m.group(1)} EUR", number))
    return out


def enrich(notice: Notice, pages: Optional[list[str]]) -> Notice:
    """Attach document findings and 'to check' flags. pages=None means the
    documents were not available at all (nothing is claimed about them)."""
    if pages is None:
        return notice
    if not any(p.strip() for p in pages):
        notice.flags.append("NO_TEXT_LAYER")
        return notice

    notice.requirements = find_requirements(pages)
    notice.doc_deadline = find_deadline(pages)
    doc = notice.doc_deadline

    if doc is None:
        if notice.deadline is None:
            notice.flags.append("DEADLINE_MISSING")
        return notice
    if doc.confidence == "CHECK":
        notice.flags.append("DEADLINE_UNCERTAIN")
    if notice.deadline is not None and doc.value and doc.value != notice.deadline_key():
        notice.flags.append("DEADLINE_MISMATCH")
    if notice.deadline is None and not doc.value:
        notice.flags.append("DEADLINE_MISSING")
    return notice
