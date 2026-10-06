from datetime import date
from decimal import Decimal

import pytest

from checks import hinweise, unterschiede, unterschiede_text
from models import Laborierung
from units import fmt_decimal, parse_date, parse_decimal


@pytest.mark.parametrize("eingabe, erwartet", [
    ("5,5", Decimal("5.5")), ("5.5", Decimal("5.5")), (" 31,20 mm", Decimal("31.20")),
    ("200 gr", Decimal("200")), ("1.234,5", Decimal("1234.5")), ("", None), (None, None),
])
def test_parse_decimal(eingabe, erwartet):
    assert parse_decimal(eingabe) == erwartet


@pytest.mark.parametrize("eingabe", ["abc", "5,5,5", "nan", "inf"])
def test_parse_decimal_ungueltig(eingabe):
    with pytest.raises(ValueError):
        parse_decimal(eingabe)


def test_fmt_decimal_dezimalkomma():
    assert fmt_decimal(Decimal("31.200")) == "31,2"
    assert fmt_decimal(Decimal("200.000")) == "200"
    assert fmt_decimal(Decimal("11.99")) == "11,99"
    assert fmt_decimal(None) == ""


def test_parse_date():
    assert parse_date("2026-10-05") == date(2026, 10, 5)
    assert parse_date("05.10.2026") == date(2026, 10, 5)


def _lab(**kw):
    basis = dict(name="T", kaliber=".45 ACP", status="entwurf")
    return Laborierung(**(basis | kw))


def test_warnung_wenn_ladung_ueber_max():
    h = hinweise(_lab(ladung_gr=Decimal("5.6"), max_ladung_gr=Decimal("5.5"), quelle="Hodgdon"))
    assert [x.stufe for x in h] == ["warnung"]
    assert "5,6 gr" in h[0].text and "5,5 gr" in h[0].text


def test_keine_warnung_bei_gleicher_ladung():
    assert hinweise(_lab(ladung_gr=Decimal("5.5"), max_ladung_gr=Decimal("5.50"), quelle="Hodgdon")) == []


def test_hinweis_bei_fehlender_quelle():
    h = hinweise(_lab(ladung_gr=Decimal("5.5")))
    assert len(h) == 1 and h[0].stufe == "info" and "Quelle" in h[0].text


def test_hinweis_bei_fehlender_max_ladung():
    h = hinweise(_lab(ladung_gr=Decimal("5.5"), quelle="Handbuch"))
    assert [x.stufe for x in h] == ["info"] and "Max-Ladung" in h[0].text


def test_keine_warnung_ohne_ladung():
    assert all(x.stufe != "warnung" for x in hinweise(_lab(max_ladung_gr=Decimal("5.5"))))


def test_unterschiede_zum_vorgaenger():
    alt = _lab(l6_mm=Decimal("30.5"), pulver="HP-38", name="A")
    neu = _lab(l6_mm=Decimal("31.2"), pulver="HP-38", name="B", status="in_test")
    assert unterschiede(alt, neu) == [("L6 (Gesamtlänge)", "30,5 mm", "31,2 mm")]
    assert unterschiede_text(alt, neu) == "L6 (Gesamtlänge) 30,5 mm → 31,2 mm"


def test_etikettgroesse_parsen():
    from labels import parse_size
    assert parse_size("70x50") == (70, 50)
    assert parse_size(" 100 × 70 ") == (100, 70)
    assert parse_size("10x10") == (90, 60)  # zu klein
    assert parse_size(" " * 10000 + "x") == (90, 60)  # lange Eingabe, kein Backtracking
