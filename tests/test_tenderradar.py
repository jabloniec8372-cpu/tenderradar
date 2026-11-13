import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import demo
from tenderradar import ted
from tenderradar.digest import render_text
from tenderradar.extract import enrich, find_deadline, find_requirements, split_pages
from tenderradar.match import evaluate
from tenderradar.models import TZ, Notice, Profile
from tenderradar.pipeline import run
from tenderradar.store import AMENDED, DEADLINE_CHANGED, NEW, UNCHANGED, Store

NOW = datetime(2026, 11, 13, 18, 30, tzinfo=TZ)
PROFILE = Profile.from_dict(
    {"name": "t", "nuts_prefixes": ["DE4"], "cpv_prefixes": ["9091"], "keywords": ["reinigung"]}
)


def make_notice(**kw) -> Notice:
    base = dict(
        procedure_id="p1", publication_number="1-2026", title="Reinigung Schule",
        buyer="Stadt", nuts=["DE40"], cpv=["90911200"], published="2026-11-12",
        deadline=datetime(2026, 11, 27, 10, 0, tzinfo=TZ), url="u",
    )
    base.update(kw)
    return Notice(**base)


class ExtractTests(unittest.TestCase):
    def test_strict_deadline_is_ok_and_has_page(self):
        f = find_deadline(["intro", "Angebotsfrist: 27.11.2026, 10:00 Uhr"])
        self.assertEqual((f.value, f.page, f.confidence), ("2026-11-27T10:00", 2, "OK"))

    def test_ocr_confusions_are_repaired_but_marked_check(self):
        f = find_deadline(["Abgabefrist: 04.12.2O26, 11:OO Uhr"])
        self.assertEqual(f.value, "2026-12-04T11:00")
        self.assertEqual(f.confidence, "CHECK")

    def test_impossible_date_is_check_not_a_guess(self):
        f = find_deadline(["Angebotsfrist: 45.13.2026"])
        self.assertEqual(f.confidence, "CHECK")
        self.assertEqual(f.value, "")

    def test_no_deadline_in_text(self):
        self.assertIsNone(find_deadline(["nothing here"]))

    def test_requirements_words_and_digits(self):
        r = find_requirements(["mindestens zwei Referenzen", "Jahresumsatz von mindestens 1.500.000 EUR", "min. 3 Referenz"])
        self.assertEqual([x.value for x in r], [">=2 references", "annual turnover >= 1.500.000 EUR", ">=3 references"])
        self.assertEqual([x.page for x in r], [1, 2, 3])

    def test_empty_scan_is_flagged_not_skipped(self):
        n = enrich(make_notice(), split_pages("\f\f"))
        self.assertEqual(n.flags, ["NO_TEXT_LAYER"])

    def test_mismatch_between_api_and_document(self):
        n = enrich(make_notice(), ["Angebotsfrist: 28.11.2026, 10:00"])
        self.assertIn("DEADLINE_MISMATCH", n.flags)

    def test_matching_document_has_no_flags(self):
        n = enrich(make_notice(), ["Angebotsfrist: 27.11.2026, 10:00"])
        self.assertEqual(n.flags, [])

    def test_documents_not_available_claims_nothing(self):
        self.assertEqual(enrich(make_notice(), None).flags, [])


class MatchTests(unittest.TestCase):
    def test_match_explains_itself(self):
        m = evaluate(make_notice(), PROFILE, NOW)
        self.assertTrue(m.matched)
        self.assertEqual(m.reasons, ["region DE40", "CPV 90911200", 'keyword "reinigung"'])

    def test_outside_region(self):
        self.assertIn("outside region", evaluate(make_notice(nuts=["DE21"]), PROFILE, NOW).rejections)

    def test_wrong_trade(self):
        m = evaluate(make_notice(title="IT", cpv=["72000000"]), PROFILE, NOW)
        self.assertFalse(m.matched)

    def test_expired(self):
        n = make_notice(deadline=datetime(2026, 11, 1, tzinfo=TZ))
        self.assertIn("deadline passed", evaluate(n, PROFILE, NOW).rejections)


class StoreTests(unittest.TestCase):
    def test_event_sequence(self):
        s = Store()
        n = make_notice()
        self.assertEqual(s.upsert(n), (NEW, None))
        self.assertEqual(s.upsert(n), (UNCHANGED, None))
        self.assertEqual(s.upsert(make_notice(publication_number="2-2026")), (AMENDED, "2026-11-27T10:00"))
        moved = make_notice(publication_number="3-2026", deadline=datetime(2026, 12, 4, 10, 0, tzinfo=TZ))
        self.assertEqual(s.upsert(moved), (DEADLINE_CHANGED, "2026-11-27T10:00"))


class TedTests(unittest.TestCase):
    def test_multilingual_and_missing_fields(self):
        n = ted.parse_notice({
            "publication-number": "9-2026",
            "notice-title": {"eng": "Cleaning", "deu": "Reinigung"},
            "buyer-name": {"deu": ["Stadt X"]},
            "publication-date": "2026-11-12+01:00",
        })
        self.assertEqual((n.title, n.buyer, n.published), ("Reinigung", "Stadt X", "2026-11-12"))
        self.assertIsNone(n.deadline)
        self.assertEqual(n.procedure_id, "9-2026")  # falls back to publication number
        self.assertTrue(n.url.endswith("9-2026"))

    def test_earliest_lot_deadline_wins(self):
        n = ted.parse_notice({"publication-number": "1", "deadline-receipt-tender-date-lot": [
            "2026-12-04T10:00:00+01:00", "2026-11-27T10:00:00+01:00", "garbage"]})
        self.assertEqual(n.deadline_key(), "2026-11-27T10:00")

    def test_pagination_follows_token_and_stops(self):
        pages = [{"notices": [{"a": 1}, {"a": 2}], "iterationNextToken": "t1"},
                 {"notices": [{"a": 3}]}]
        calls = []

        def fake_post(url, body):
            calls.append(body)
            return pages[len(calls) - 1]

        got = list(ted.search("q", post=fake_post))
        self.assertEqual(len(got), 3)
        self.assertNotIn("iterationNextToken", calls[0])
        self.assertEqual(calls[1]["iterationNextToken"], "t1")

    def test_query_is_simple_and_debuggable(self):
        self.assertEqual(ted.build_query("DEU", "20261110"),
                         "place-of-performance IN (DEU) AND publication-date>=20261110")


class PipelineTests(unittest.TestCase):
    RAW = [{"publication-number": "1-2026", "procedure-identifier": "p1",
            "notice-title": {"deu": "Reinigung Schule"}, "buyer-name": {"deu": ["Stadt"]},
            "place-of-performance": ["DE40"], "classification-cpv": ["90911200"],
            "deadline-receipt-tender-date-lot": ["2026-11-27T10:00:00+01:00"]}]

    def test_alert_repeats_until_marked_sent_then_never(self):
        s = Store()
        first = run(self.RAW, PROFILE, s, NOW)
        self.assertEqual(len(first.items), 1)
        # crash before delivery: nothing marked, so the next run must not lose it
        s2 = Store()
        again = run(self.RAW, PROFILE, s2, NOW)
        self.assertEqual(len(again.items), 1)
        s.mark_sent(first.keys)
        self.assertEqual(run(self.RAW, PROFILE, s, NOW).items, [])


class DemoTests(unittest.TestCase):
    def test_demo_story(self):
        out = demo.main("en")
        self.assertIn("Day 1 (Fri 13.11.2026) - 3 to report, 2 filtered out", out)
        self.assertIn("[DEADLINE CHANGED: 27.11.2026 10:00 -> 04.12.2026 10:00]", out)
        self.assertIn("no text layer", out)
        self.assertIn("differs from the notice data", out)
        # the unchanged Berlin tender must not be reported again on day 2
        self.assertEqual(out.count("Rathaus"), 1)

    def test_other_languages_render(self):
        self.assertIn("FRIST GEÄNDERT", demo.main("de"))
        self.assertIn("ZMIANA TERMINU", demo.main("pl"))


if __name__ == "__main__":
    unittest.main()
