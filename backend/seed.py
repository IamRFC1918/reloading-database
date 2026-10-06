"""Beispieldatensatz, damit die Oberfläche nach der Installation nicht leer ist.
Die Werte sind KEINE Ladeempfehlung. Nur in eine leere Datenbank, und nur mit
SEED_DEMO_DATA=true (Standard: aus)."""
from datetime import date
from decimal import Decimal

import storage
from models import Laborierung, Testserie
from storage import Session


def seed_demo_daten():
    if storage.anzahl_laborierungen():
        return False
    lab = Laborierung(
        name="Beispiel – .45 ACP SWC 200 gr / HP-38 (keine Ladeempfehlung)",
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
        notiz="Beispieldatensatz zum Ausprobieren der App – keine Ladeempfehlung. "
        "Vor eigener Verwendung immer mit aktuellen Herstellerdaten abgleichen.",
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
