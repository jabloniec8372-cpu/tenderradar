"""Offline demo: two days of (synthetic) TED data for a cleaning company.

    python3 demo.py

Day 1: new tenders arrive; one is outside the region, one is IT, one is a scan.
Day 2: the buyer extends a deadline (published as a correction notice) and a
new tender appears whose document disagrees with the API data.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from tenderradar.cli import _fixture_source
from tenderradar.digest import render_text
from tenderradar.models import TZ, Profile
from tenderradar.pipeline import commit, run
from tenderradar.store import Store

HERE = Path(__file__).parent
FIX = HERE / "fixtures"


def ensure_fixtures() -> None:
    if not (FIX / "day2" / "notices.json").exists():
        import importlib.util

        spec = importlib.util.spec_from_file_location("make_fixtures", FIX / "make_fixtures.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.generate()


def day(label: str, folder: str, now: datetime, store: Store, profile: Profile, lang: str = "en") -> str:
    raw, docs = _fixture_source(FIX / folder)
    report = run(raw, profile, store, now, docs)
    commit(store, report)
    head = f"=== {label} ({now:%a %d.%m.%Y}) - {len(report.items)} to report, {report.rejected} filtered out ===\n"
    return head + "\n" + render_text(report, lang)


def main(lang: str = "en") -> str:
    ensure_fixtures()
    profile = Profile.from_dict(json.loads((FIX / "profile_cleaning_brandenburg.json").read_text(encoding="utf-8")))
    store = Store()  # in memory
    out = day("Day 1", "day1", datetime(2026, 11, 13, 18, 30, tzinfo=TZ), store, profile, lang)
    out += "\n" + day("Day 2", "day2", datetime(2026, 11, 16, 8, 0, tzinfo=TZ), store, profile, lang)
    return out


if __name__ == "__main__":
    print(main())
