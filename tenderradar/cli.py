"""Command line: python -m tenderradar run ..."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from . import mailer, ted
from .digest import render_html, render_text
from .extract import split_pages
from .models import TZ, Profile
from .pipeline import commit, run
from .store import Store


def _fixture_source(folder: Path):
    data = json.loads((folder / "notices.json").read_text(encoding="utf-8"))

    def docs(notice):
        path = folder / "docs" / f"{notice.publication_number}.txt"
        return split_pages(path.read_text(encoding="utf-8")) if path.exists() else None

    return data["notices"], docs


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tenderradar")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="fetch, match and write today's digest")
    r.add_argument("--profile", required=True, help="client profile JSON")
    r.add_argument("--source", choices=["fixtures", "ted"], default="fixtures")
    r.add_argument("--fixtures", help="folder with notices.json (+ docs/)")
    r.add_argument("--days", type=int, default=3, help="TED: look back N days")
    r.add_argument("--db", default="tenderradar.db")
    r.add_argument("--out", default="out")
    r.add_argument("--lang", choices=["en", "de", "pl"], default="en")
    r.add_argument("--mail-to", help="comma-separated recipients; SMTP settings come from the environment: "
                   "SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, MAIL_FROM")
    r.add_argument("--mail-empty", action="store_true", help="also send a digest when nothing is new")
    args = p.parse_args(argv)

    profile = Profile.from_dict(json.loads(Path(args.profile).read_text(encoding="utf-8")))
    now = datetime.now(TZ)

    if args.source == "fixtures":
        if not args.fixtures:
            p.error("--fixtures is required with --source fixtures")
        raw, docs = _fixture_source(Path(args.fixtures))
    else:  # live TED API
        since = (now - timedelta(days=args.days)).strftime("%Y%m%d")
        raw = ted.search(ted.build_query("DEU", since))
        docs = None  # v1: documents are not downloaded from TED

    store = Store(args.db)
    report = run(raw, profile, store, now, docs)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    text, html = render_text(report, args.lang), render_html(report, args.lang)
    (out / "digest.txt").write_text(text, encoding="utf-8")
    (out / "digest.html").write_text(html, encoding="utf-8")

    if args.mail_to and (report.items or args.mail_empty):
        try:
            msg = mailer.build_message(
                f"TenderRadar: {len(report.items)} new/changed tender(s)", text, html,
                os.environ.get("MAIL_FROM", os.environ.get("SMTP_USER", "tenderradar@localhost")),
                [a.strip() for a in args.mail_to.split(",") if a.strip()],
            )
            mailer.send(msg, os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "587")),
                        os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD"))
        except Exception as e:  # nothing is marked as sent: the next run tries again
            print(f"e-mail failed ({type(e).__name__}: {e}); alerts stay pending")
            store.close()
            return 1
    # Marked only after the digest was written (and e-mailed, if asked):
    # a crash in between re-sends, never loses.
    commit(store, report)
    store.close()
    print(f"{len(report.items)} to report, {report.rejected} filtered out -> {out}/digest.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
