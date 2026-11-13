"""One run: raw notices in, a report of what is new or changed out."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable, Optional

from .extract import enrich
from .match import Match, evaluate
from .models import Notice, Profile
from .store import UNCHANGED, Store
from .ted import parse_notice


@dataclass
class Item:
    event: str
    notice: Notice
    match: Match
    previous_deadline: Optional[str] = None


@dataclass
class Report:
    items: list[Item] = field(default_factory=list)
    rejected: int = 0
    keys: list[str] = field(default_factory=list)  # pass to Store.mark_sent after delivery


def run(
    raw_notices: Iterable[dict],
    profile: Profile,
    store: Store,
    now: datetime,
    docs: Optional[Callable[[Notice], Optional[list[str]]]] = None,
) -> Report:
    """Alerts are only *recorded* as sent via store.mark_sent(report.keys), which
    the caller does after the digest was delivered. A crash before that means
    the next run re-sends instead of silently losing an alert."""
    report = Report()
    for raw in raw_notices:
        notice = parse_notice(raw)
        enrich(notice, docs(notice) if docs else None)
        match = evaluate(notice, profile, now)
        if not match.matched:
            report.rejected += 1
            continue
        event, previous = store.upsert(notice)
        if event == UNCHANGED:
            continue
        key = f"{notice.procedure_id}|{event}|{notice.deadline_key()}"
        if store.was_sent(key):
            continue
        report.items.append(Item(event, notice, match, previous))
        report.keys.append(key)
    report.items.sort(key=lambda i: i.notice.deadline_key() or "9999")
    return report
