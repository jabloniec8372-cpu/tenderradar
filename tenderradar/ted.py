"""Client and parser for the official TED Search API v3.

TED publishes EU procurement notices through an open API (no key needed for
read-only search), so nothing here scrapes HTML.

    POST https://api.ted.europa.eu/v3/notices/search

The HTTP call is injected (`post`), so the whole module is testable offline.
"""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Callable, Iterator, Optional

from .models import Notice

TED_URL = "https://api.ted.europa.eu/v3/notices/search"

FIELDS = [
    "publication-number",
    "procedure-identifier",
    "notice-title",
    "buyer-name",
    "place-of-performance",
    "classification-cpv",
    "publication-date",
    "deadline-receipt-tender-date-lot",
    "links",
]

LANG_PREFERENCE = ["deu", "eng", "pol"]


def build_query(country_alpha3: str, published_from: str) -> str:
    """Server-side filter: country + publication date (YYYYMMDD).

    Region (NUTS) and CPV matching happen client-side in match.py, so the
    query stays simple and easy to debug in TED's Expert Search page.
    """
    return f"place-of-performance IN ({country_alpha3}) AND publication-date>={published_from}"


def default_post(url: str, body: dict) -> dict:  # pragma: no cover - needs network
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search(
    query: str,
    post: Callable[[str, dict], dict] = default_post,
    limit: int = 100,
    max_pages: int = 5,
) -> Iterator[dict]:
    """Yield raw notices, following TED's iteration token. Bounded by max_pages."""
    token: Optional[str] = None
    for _ in range(max_pages):
        body = {
            "query": query,
            "fields": FIELDS,
            "limit": limit,
            "scope": "ACTIVE",
            "paginationMode": "ITERATION",
        }
        if token:
            body["iterationNextToken"] = token
        data = post(TED_URL, body)
        notices = data.get("notices", [])
        yield from notices
        token = data.get("iterationNextToken")
        if not token or not notices:
            return


# ---------------------------------------------------------------- parsing


def _pick(value):
    """TED returns multilingual text as {lang: text-or-list}. Pick one string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return _pick(value[0]) if value else ""
    if isinstance(value, dict):
        for lang in LANG_PREFERENCE:
            if lang in value:
                return _pick(value[lang])
        return _pick(next(iter(value.values()), ""))
    return str(value)


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def parse_notice(raw: dict) -> Notice:
    pn = _pick(raw.get("publication-number"))
    deadlines = []
    for item in _as_list(raw.get("deadline-receipt-tender-date-lot")):
        try:
            deadlines.append(datetime.fromisoformat(str(item)))
        except ValueError:
            continue  # unparseable value: treated as "no deadline", flagged later
    links = raw.get("links", {}).get("htmlDirect", {})
    url = _pick({k.casefold(): v for k, v in links.items()}) if links else ""
    return Notice(
        procedure_id=_pick(raw.get("procedure-identifier")) or pn,
        publication_number=pn,
        title=_pick(raw.get("notice-title")).strip(),
        buyer=_pick(raw.get("buyer-name")).strip(),
        nuts=[str(x) for x in _as_list(raw.get("place-of-performance"))],
        cpv=[str(x) for x in _as_list(raw.get("classification-cpv"))],
        published=str(raw.get("publication-date", ""))[:10] or None,
        deadline=min(deadlines) if deadlines else None,
        url=url or f"https://ted.europa.eu/en/notice/-/detail/{pn}",
    )
