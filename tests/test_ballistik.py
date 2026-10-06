from datetime import date
from decimal import Decimal

import pytest

import ballistik
import charts
from models import Laborierung, Testserie


def test_messreihe_parsen_mit_komma_und_zeilen():
    werte = ballistik.parse_messreihe("251,3 249\n253.8;250")
    assert werte == [Decimal("251.3"), Decimal("249"), Decimal("253.8"), Decimal("250")]
    assert ballistik.als_text(werte) == "251.3 249 253.8 250"
    assert ballistik.parse_messreihe("  ") == []
    assert ballistik.als_text([]) is None


def test_messreihe_fps_wird_in_ms_umgerechnet():
    assert ballistik.parse_messreihe("820 830", "fps") == [Decimal("249.9"), Decimal("253.0")]


@pytest.mark.parametrize("text", ["251 abc", "-3", "0", "2500"])
def test_messreihe_ungueltig(text):
    with pytest.raises(ValueError):
        ballistik.parse_messreihe(text)


def test_statistik():
    s = ballistik.statistik([Decimal("250"), Decimal("252"), Decimal("248"), Decimal("254")])
    assert s.n == 4 and s.mittel == 251
    assert s.es == 6
    assert s.sd == pytest.approx(2.582, abs=0.001)
    assert s.cv == pytest.approx(1.029, abs=0.001)
    einzeln = ballistik.statistik([Decimal("250")])
    assert einzeln.sd is None and einzeln.cv is None and einzeln.es == 0


def test_energie_und_power_factor():
    # 200 gr = 12,96 g bei 250 m/s -> 405 J; 250 m/s = 820,2 fps -> PF 164,0
    assert ballistik.energie_j(200, 250) == pytest.approx(405.0, abs=0.1)
    assert ballistik.power_factor(200, 250) == pytest.approx(164.04, abs=0.01)
    assert ballistik.fps(250) == pytest.approx(820.21, abs=0.01)


def test_auswerten_bevorzugt_einzelwerte():
    lab = Laborierung(name="x", kaliber=".45 ACP", geschoss_gewicht_gr=Decimal("200"))
    serie = Testserie(datum=date.today(), v_einzelwerte="250 252", geschwindigkeit_ms=Decimal("999"))
    serie.laborierung = lab
    a = ballistik.auswerten(serie)
    assert a.einzelwerte and a.stat.mittel == 251 and a.energie_j > 0
    nur_mittel = Testserie(datum=date.today(), geschwindigkeit_ms=Decimal("250"))
    nur_mittel.laborierung = Laborierung(name="y", kaliber=".45 ACP")
    a = ballistik.auswerten(nur_mittel)
    assert not a.einzelwerte and a.energie_j is None and a.power_factor is None
    assert ballistik.auswerten(Testserie(datum=date.today())) is None


def test_diagramme_sind_svg_und_escapen():
    svg = charts.schuss_diagramm([Decimal("250"), Decimal("252.5"), Decimal("248")])
    assert svg.startswith("<svg") and svg.count("<circle") == 6  # je Schuss Punkt + Trefferfläche
    assert "Schuss 2: 252,5 m/s" in svg
    eintraege = [{"label": "01.10.", "gruppe": 0, "mittel": 250.0, "sd": 2.0, "tipp": "<b>Serie</b>"},
                 {"label": "05.10.", "gruppe": 1, "mittel": 255.0, "sd": None, "tipp": "Serie 2"}]
    svg = charts.vergleich_diagramm(eintraege)
    assert "&lt;b&gt;Serie&lt;/b&gt;" in svg and "<b>" not in svg
    assert charts.schuss_diagramm([]) == ""
