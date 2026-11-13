"""Data model. Everything the pipeline passes around is defined here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Berlin")


@dataclass
class Finding:
    """A value read from a tender document, with where it came from.

    confidence is "OK" (strict match) or "CHECK" (a human should look at it).
    """

    value: str
    page: Optional[int]
    confidence: str = "OK"
    note: str = ""


@dataclass
class Notice:
    procedure_id: str  # stable across amendments; links a notice to its changes
    publication_number: str  # changes with every published version
    title: str
    buyer: str
    nuts: list[str]
    cpv: list[str]
    published: Optional[str]  # YYYY-MM-DD
    deadline: Optional[datetime]
    url: str
    pdf_url: str = ""  # the notice as PDF on TED, if the API gave a link
    doc_deadline: Optional[Finding] = None
    requirements: list[Finding] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)  # reasons for "to be checked"

    def deadline_key(self) -> str:
        """Deadline as local, minute-precision text. Used to detect changes."""
        if self.deadline is None:
            return ""
        return self.deadline.astimezone(TZ).strftime("%Y-%m-%dT%H:%M")


@dataclass
class Profile:
    """What the client is looking for."""

    name: str
    nuts_prefixes: list[str]
    cpv_prefixes: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    min_days_to_deadline: int = 3

    @staticmethod
    def from_dict(d: dict) -> "Profile":
        return Profile(
            name=d["name"],
            nuts_prefixes=list(d["nuts_prefixes"]),
            cpv_prefixes=list(d.get("cpv_prefixes", [])),
            keywords=[k.casefold() for k in d.get("keywords", [])],
            min_days_to_deadline=int(d.get("min_days_to_deadline", 3)),
        )
