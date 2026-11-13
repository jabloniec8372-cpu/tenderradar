"""Render a Report as a plain-text and HTML digest (en / de / pl)."""
from __future__ import annotations

import html
from datetime import datetime

from .pipeline import Report

L = {
    "en": {
        "title": "Tender digest",
        "none": "No new or changed tenders today.",
        "NEW": "NEW",
        "DEADLINE_CHANGED": "DEADLINE CHANGED",
        "AMENDED": "AMENDED",
        "deadline": "Deadline",
        "why": "Why it fits",
        "req": "Requirements",
        "check": "TO CHECK",
        "page": "p.",
        "open": "Open",
        "no_deadline": "not stated",
        "flags": {
            "NO_TEXT_LAYER": "document has no text layer (scan) - OCR needed",
            "DEADLINE_UNCERTAIN": "deadline in document was read with OCR-style repair",
            "DEADLINE_MISMATCH": "deadline in document differs from the notice data",
            "DEADLINE_MISSING": "no deadline found",
        },
    },
    "de": {
        "title": "Ausschreibungs-Übersicht",
        "none": "Heute keine neuen oder geänderten Ausschreibungen.",
        "NEW": "NEU",
        "DEADLINE_CHANGED": "FRIST GEÄNDERT",
        "AMENDED": "BERICHTIGT",
        "deadline": "Frist",
        "why": "Passt weil",
        "req": "Anforderungen",
        "check": "ZU PRÜFEN",
        "page": "S.",
        "open": "Öffnen",
        "no_deadline": "nicht angegeben",
        "flags": {
            "NO_TEXT_LAYER": "Dokument ohne Textebene (Scan) - OCR nötig",
            "DEADLINE_UNCERTAIN": "Frist im Dokument nur unsicher gelesen (OCR-Korrektur)",
            "DEADLINE_MISMATCH": "Frist im Dokument weicht von den Bekanntmachungsdaten ab",
            "DEADLINE_MISSING": "keine Frist gefunden",
        },
    },
    "pl": {
        "title": "Zestawienie przetargów",
        "none": "Dziś brak nowych lub zmienionych przetargów.",
        "NEW": "NOWY",
        "DEADLINE_CHANGED": "ZMIANA TERMINU",
        "AMENDED": "ZMIENIONE OGŁOSZENIE",
        "deadline": "Termin ofert",
        "why": "Dlaczego pasuje",
        "req": "Wymagania",
        "check": "DO SPRAWDZENIA",
        "page": "s.",
        "open": "Otwórz",
        "no_deadline": "brak",
        "flags": {
            "NO_TEXT_LAYER": "dokument bez warstwy tekstowej (skan) - potrzebny OCR",
            "DEADLINE_UNCERTAIN": "termin w dokumencie odczytany niepewnie (korekta OCR)",
            "DEADLINE_MISMATCH": "termin w dokumencie różni się od danych ogłoszenia",
            "DEADLINE_MISSING": "nie znaleziono terminu",
        },
    },
}


def _fmt(key: str, fallback: str) -> str:
    if not key:
        return fallback
    return datetime.strptime(key, "%Y-%m-%dT%H:%M").strftime("%d.%m.%Y %H:%M")


def _lines(report: Report, lang: str) -> list[tuple[str, list[str]]]:
    t = L[lang]
    blocks = []
    for it in report.items:
        n = it.notice
        label = t[it.event]
        if it.event == "DEADLINE_CHANGED":
            label += f": {_fmt(it.previous_deadline or '', t['no_deadline'])} -> {_fmt(n.deadline_key(), t['no_deadline'])}"
        head = f"[{label}] {n.title} - {n.buyer}"
        body = [
            f"{t['deadline']}: {_fmt(n.deadline_key(), t['no_deadline'])}",
            f"{t['why']}: {', '.join(it.match.reasons + it.match.warnings)}",
        ]
        if n.requirements:
            body.append(
                f"{t['req']}: "
                + "; ".join(f"{r.value} ({t['page']} {r.page})" for r in n.requirements)
            )
        for flag in n.flags:
            where = ""
            if n.doc_deadline and flag.startswith("DEADLINE") and n.doc_deadline.page:
                where = f" ({t['page']} {n.doc_deadline.page})"
            body.append(f"!! {t['check']}: {t['flags'][flag]}{where}")
        body.append(f"{t['open']}: {n.url}")
        blocks.append((head, body))
    return blocks


def render_text(report: Report, lang: str = "en") -> str:
    t = L[lang]
    out = [t["title"], "=" * len(t["title"]), ""]
    blocks = _lines(report, lang)
    if not blocks:
        out.append(t["none"])
    for head, body in blocks:
        out.append(head)
        out.extend("   " + b for b in body)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_html(report: Report, lang: str = "en") -> str:
    t = L[lang]
    parts = [f"<h2>{html.escape(t['title'])}</h2>"]
    blocks = _lines(report, lang)
    if not blocks:
        parts.append(f"<p>{html.escape(t['none'])}</p>")
    for head, body in blocks:
        parts.append(f"<h3>{html.escape(head)}</h3><ul>")
        for b in body:
            cls = ' style="color:#b45309"' if b.startswith("!!") else ""
            parts.append(f"<li{cls}>{html.escape(b)}</li>")
        parts.append("</ul>")
    return "\n".join(parts)
