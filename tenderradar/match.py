"""Decide whether a notice fits the client, and say why (or why not)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import TZ, Notice, Profile


@dataclass
class Match:
    matched: bool
    reasons: list[str] = field(default_factory=list)
    rejections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def evaluate(notice: Notice, profile: Profile, now: datetime) -> Match:
    m = Match(matched=False)

    region_hits = [
        n for n in notice.nuts if any(n.startswith(p) for p in profile.nuts_prefixes)
    ]
    if region_hits:
        m.reasons.append(f"region {region_hits[0]}")
    else:
        m.rejections.append("outside region")

    cpv_hits = [c for c in notice.cpv if any(c.startswith(p) for p in profile.cpv_prefixes)]
    title = notice.title.casefold()
    kw_hits = [k for k in profile.keywords if k in title]
    if cpv_hits:
        m.reasons.append(f"CPV {cpv_hits[0]}")
    if kw_hits:
        m.reasons.append(f'keyword "{kw_hits[0]}"')
    if not cpv_hits and not kw_hits:
        m.rejections.append("no CPV or keyword match")

    if notice.deadline is not None:
        remaining = notice.deadline.astimezone(TZ) - now.astimezone(TZ)
        if remaining.total_seconds() <= 0:
            m.rejections.append("deadline passed")
        elif remaining.days < profile.min_days_to_deadline:
            m.warnings.append(f"deadline in {remaining.days} day(s)")

    m.matched = not m.rejections
    return m
