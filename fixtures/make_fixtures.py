"""Generates the synthetic demo data (notices shaped like TED responses,
tender documents with form-feed page breaks, and a client profile).

Run directly, or let demo.py call generate() when fixtures are missing.
"""
import json
import pathlib

root = pathlib.Path(__file__).resolve().parent


def generate():
    for d in ('day1/docs', 'day2/docs'):
        (root / d).mkdir(parents=True, exist_ok=True)
    PID = lambda n: f"00000000-0000-4000-8000-{n:012d}"

    def notice(pn, pid, title, buyer, nuts, cpv, deadline, pub="2026-11-12"):
        return {
            "publication-number": pn, "procedure-identifier": PID(pid),
            "notice-title": {"deu": title},
            "buyer-name": {"deu": [buyer]},
            "place-of-performance": nuts, "classification-cpv": cpv,
            "publication-date": pub + "+01:00",
            "deadline-receipt-tender-date-lot": [deadline] if deadline else [],
            "links": {"htmlDirect": {"DEU": f"https://ted.europa.eu/de/notice/-/detail/{pn}"}},
        }

    day1 = [
        notice("700001-2026", 1, "Unterhaltsreinigung von zwei Schulen im Landkreis Potsdam-Mittelmark",
               "Landkreis Potsdam-Mittelmark", ["DE40"], ["90911200"], "2026-11-27T10:00:00+01:00"),
        notice("700002-2026", 2, "Winterdienst auf Kreisstraßen",
               "Landkreis Rosenheim", ["DE21"], ["90620000"], "2026-12-01T12:00:00+01:00"),
        notice("700003-2026", 3, "Gebäudereinigung Rathaus Charlottenburg-Wilmersdorf",
               "Bezirksamt Charlottenburg-Wilmersdorf", ["DE30"], ["90911000"], "2026-12-04T11:00:00+01:00"),
        notice("700004-2026", 4, "Rahmenvertrag IT-Dienstleistungen",
               "Land Brandenburg", ["DE40"], ["72000000"], "2026-12-02T09:00:00+01:00"),
        notice("700006-2026", 6, "Reinigung Schwimmhalle Cottbus",
               "Stadt Cottbus", ["DE40"], ["90911200"], "2026-11-15T10:00:00+01:00"),
    ]
    day2 = [
        # correction notice for procedure 1: new publication number, deadline moved
        notice("700101-2026", 1, "Unterhaltsreinigung von zwei Schulen im Landkreis Potsdam-Mittelmark",
               "Landkreis Potsdam-Mittelmark", ["DE40"], ["90911200"], "2026-12-04T10:00:00+01:00", "2026-11-16"),
        day1[2],  # unchanged
        notice("700005-2026", 5, "Glas- und Fensterreinigung Landratsamt Oberhavel",
               "Landkreis Oberhavel", ["DE40"], ["90911300"], "2026-12-10T12:00:00+01:00", "2026-11-16"),
    ]
    for d, items in (("day1", day1), ("day2", day2)):
        (root / d / "notices.json").write_text(
            json.dumps({"notices": items}, ensure_ascii=False, indent=1), encoding="utf-8")

    def doc(*pages):  # form feed between pages, like pdftotext
        return "\f".join(pages)

    filler = lambda t: f"Vergabeunterlagen - {t}\nAllgemeine Angaben zum Verfahren."
    (root / "day1/docs/700001-2026.txt").write_text(doc(
        filler("Unterhaltsreinigung Schulen"),
        "Leistungsbeschreibung: Reinigung zweier Schulgebäude, 5 Tage pro Woche.",
        "Angebotsfrist: 27.11.2026, 10:00 Uhr\nBindefrist: 31.01.2027",
        "Hinweise zur Angebotsabgabe über die Vergabeplattform.",
        "Eignungsnachweis: Der Bieter weist mindestens zwei Referenzen über vergleichbare\n"
        "Reinigungsleistungen nach. Jahresumsatz von mindestens 250.000 EUR in den letzten drei Jahren.",
    ), encoding="utf-8")
    # scanned-looking document: OCR confused 0 and O
    (root / "day1/docs/700003-2026.txt").write_text(doc(
        filler("Gebäudereinigung Rathaus"),
        "Abgabefrist: 04.12.2O26, 11:OO Uhr\nZuschlagskriterium: Preis 60 %, Qualität 40 %",
        "Der Bieter belegt mindestens drei Referenzen aus dem öffentlichen Sektor.",
    ), encoding="utf-8")
    (root / "day1/docs/700006-2026.txt").write_text("\f\f", encoding="utf-8")  # empty scan, no text
    (root / "day2/docs/700101-2026.txt").write_text(doc(
        filler("Unterhaltsreinigung Schulen - Berichtigung"),
        "Berichtigung: Die Angebotsfrist wird verlängert.\nNeue Angebotsfrist: 04.12.2026, 10:00 Uhr",
        "Eignungsnachweis: mindestens zwei Referenzen. Jahresumsatz von mindestens 250.000 EUR.",
    ), encoding="utf-8")
    # API says 10.12. but the document says 11.12. -> mismatch must be flagged
    (root / "day2/docs/700005-2026.txt").write_text(doc(
        filler("Fensterreinigung"),
        "Frist zur Abgabe der Angebote: 11.12.2026, 12:00 Uhr",
        "Mindestens zwei Referenzen sind nachzuweisen.",
    ), encoding="utf-8")

    (root / "profile_cleaning_brandenburg.json").write_text(json.dumps({
        "name": "Reinigungsfirma Müller GmbH (demo)",
        "nuts_prefixes": ["DE3", "DE4"],
        "cpv_prefixes": ["9091", "9093"],
        "keywords": ["reinigung"],
        "min_days_to_deadline": 3,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    generate()
