from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

import storage
from models import Laborierung, Los, Testserie
from seed import seed_demo_daten


def _lab(session, **kw):
    lab = Laborierung(**({"name": "Test", "kaliber": ".45 ACP", "status": "entwurf"} | kw))
    session.add(lab)
    session.commit()
    return lab


def test_dezimalwerte_bleiben_exakt(session):
    lab = _lab(session, ladung_gr=Decimal("5.5"), l6_mm=Decimal("31.2"), huelsenmund_mm=Decimal("11.99"))
    session.expire_all()
    geladen = session.get(Laborierung, lab.id)
    assert geladen.ladung_gr == Decimal("5.5")
    assert geladen.huelsenmund_mm == Decimal("11.99")


def test_utf8_texte(session):
    lab = _lab(session, name="Hülse – „Spezial“ 🎯", geschoss_hersteller="L.O.S. Cerkno")
    session.expire_all()
    assert session.get(Laborierung, lab.id).name == "Hülse – „Spezial“ 🎯"


def test_los_nummern_fortlaufend_je_kaliber_und_jahr(session):
    lab = _lab(session)
    assert storage.naechste_los_nr(".45 ACP", 2026) == "45ACP-2026-001"
    session.add(Los(laborierung=lab, los_nr="45ACP-2026-001", anzahl=100, datum=date(2026, 1, 1)))
    session.add(Los(laborierung=lab, los_nr="45ACP-2026-007", anzahl=50, datum=date(2026, 2, 1)))
    session.commit()
    assert storage.naechste_los_nr(".45 ACP", 2026) == "45ACP-2026-008"
    assert storage.naechste_los_nr(".45 ACP", 2027) == "45ACP-2027-001"
    assert storage.naechste_los_nr("9mm Luger", 2026) == "9MMLUGER-2026-001"


def test_los_nr_eindeutig(session):
    lab = _lab(session)
    session.add(Los(laborierung=lab, los_nr="X-1", anzahl=1, datum=date.today()))
    session.add(Los(laborierung=lab, los_nr="X-1", anzahl=1, datum=date.today()))
    with pytest.raises(IntegrityError):
        session.commit()


def test_duplizieren(session):
    lab = _lab(session, pulver="HP-38", ladung_gr=Decimal("5.5"), status="freigegeben")
    lab.testserien.append(Testserie(datum=date.today(), waffe="Gold Cup"))
    session.commit()
    kopie = storage.duplizieren(lab)
    session.commit()
    assert kopie.id != lab.id
    assert kopie.vorgaenger_id == lab.id
    assert kopie.status == "entwurf"
    assert kopie.pulver == "HP-38" and kopie.ladung_gr == Decimal("5.5")
    assert kopie.testserien == []  # Erfahrungen gehören zur Vorserie


def test_testserien_werden_mit_laborierung_geloescht(session):
    lab = _lab(session)
    lab.testserien.append(Testserie(datum=date.today()))
    session.commit()
    session.delete(lab)
    session.commit()
    assert session.query(Testserie).count() == 0


def test_seed_nur_in_leere_db(session):
    assert seed_demo_daten() is True
    assert seed_demo_daten() is False
    lab = session.query(Laborierung).one()
    assert lab.l6_mm == Decimal("31.2") and lab.status == "in_test"
    assert lab.testserien[0].schlitten_schliesst is False
