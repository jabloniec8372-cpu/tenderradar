"""Get the text of a notice's PDF from TED so extract.py can read it.

What this is: the *notice* PDF that TED publishes (form data and text), not
the full tender documents. Those live on each buyer's own e-procurement
platform, differ per platform and often need registration, so they are out of
scope. Both the download and the PDF-to-text step are injectable.

Needs the `pdftotext` program (poppler-utils) for real PDFs. If it is missing
or a download fails, DocsError is raised and the pipeline flags the notice
DOCS_UNAVAILABLE instead of pretending the documents were read.
"""
from __future__ import annotations

import shutil
import subprocess
import time
import urllib.request
from typing import Callable, Optional

from .extract import split_pages
from .models import Notice

UA = "TenderRadar/0.1 (public tender monitoring; contact: owner@example.invalid)"
MAX_BYTES = 20 * 1024 * 1024


class DocsError(Exception):
    pass


def default_get_bytes(url: str) -> bytes:  # pragma: no cover - needs network
    time.sleep(1.0)  # be polite to TED between downloads
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise DocsError("document too large")
    return data


def pdf_to_text(data: bytes) -> str:
    """Uses pdftotext; pages come back separated by form feed, as extract expects."""
    exe = shutil.which("pdftotext")
    if exe is None:
        raise DocsError("pdftotext is not installed (poppler-utils)")
    proc = subprocess.run([exe, "-layout", "-", "-"], input=data, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise DocsError("pdftotext failed")
    return proc.stdout.decode("utf-8", "replace")


def make_provider(
    get_bytes: Callable[[str], bytes] = default_get_bytes,
    to_text: Callable[[bytes], str] = pdf_to_text,
) -> Callable[[Notice], Optional[list[str]]]:
    def provider(notice: Notice) -> Optional[list[str]]:
        if not notice.pdf_url:
            return None  # no document link: nothing is claimed about the documents
        try:
            return split_pages(to_text(get_bytes(notice.pdf_url)))
        except DocsError:
            raise
        except Exception as e:
            raise DocsError(f"{type(e).__name__}: {e}") from e

    return provider
