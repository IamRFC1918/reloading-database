"""Beispieldaten (eigene Angaben des Nutzers, keine Ladeempfehlung).
Werden nur in eine leere Datenbank geschrieben, abschaltbar per SEED_DEMO_DATA=false."""
from datetime import date
from decimal import Decimal

import storage
from models import Laborierung, Testserie
from storage import Session


def seed_demo_daten():
    if storage.anzahl_laborierungen():
        return False
    lab = Laborierung(
        name=".45 ACP SWC 200 gr / HP-38 – Serie 2 (L6 31,2)",
        kaliber=".45 ACP",
        geschoss_hersteller="L.O.S. Cerkno",
        geschoss_gewicht_gr=Decimal("200"),
        geschoss_durchmesser=".451",
        geschoss_art="SWC",
        pulver="HP-38",
        ladung_gr=Decimal("5.5"),
        l6_mm=Decimal("31.2"),
        huelsenlaenge_mm=Decimal("22.69"),
        huelsenmund_mm=Decimal("11.99"),
        matrizen="Hornady Custom Grade",
        status="in_test",
        datum=date.today(),
        notiz="Vorserie mit L6 30,5 mm.",
    )
    lab.testserien.append(Testserie(
        datum=date.today(),
        waffe="Colt Gold Cup",
        federstaerke="schwächere Verschlussfeder",
        schlitten_schliesst=False,
        freitext="Schlitten schloss bei einzelnen Patronen nicht ganz zu. Auswertung offen.",
        geaenderte_parameter="Neue Serie: L6 von 30,5 auf 31,2 mm, Hülsenmund stärker gecrimpt.",
    ))
    Session.add(lab)
    Session.commit()
    return True
