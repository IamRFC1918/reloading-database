import io
import json
from decimal import Decimal
from pathlib import Path

import pytest

import grt
from models import Laborierung

FIXTURE = Path(__file__).parent / "fixtures" / "grt_ladung.json"


def _roh(**ersetzen):
    daten = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for pfad, wert in ersetzen.items():
        teil, feld = pfad.split("__")
        daten[teil][feld] = wert
    return json.dumps(daten).encode()


def test_parse_werte_und_namen():
    r = grt.parse(FIXTURE.read_bytes(), "x.json")
    assert r.kaliber == ".45 ACP" and r.pulver == "Hodgdon HP-38"
    assert r.geschoss == "LOS, .45 swc, 0.451, 200.00 grain"
    assert r.ladung_gr == 5.5 and r.geschoss_gewicht_gr == 200
    assert r.oal_mm == 31.2 and r.huelsenlaenge_mm == 22.65 and r.lauflaenge_mm == 609.6
    assert r.v0_ms == 348.0 and r.pmax_bar == 904 and r.pmax_zul_bar == 1300 and r.e0_j == 785
    assert r.fuellgrad_pct == 42.5 and r.ipsc_factor == 228 and r.meldungen == []


def test_kein_lokaler_pfad_gespeichert():
    roh = json.loads(FIXTURE.read_text(encoding="utf-8"))
    roh["File"] = "C:/Users/jemand/Downloads/GRT/geheim"
    gespeichert = grt.als_json(grt.parse(json.dumps(roh)))
    assert "Users" not in gespeichert and "geheim" not in gespeichert
    assert grt.aus_json(gespeichert).v0_ms == 348.0


def test_einheiten_werden_umgerechnet():
    r = grt.parse(_roh(results__MuzzleVelocity="1141.7 ft/s", results__PeakPressure="13110 psi",
                       gun__xe="5.00 in", caliber__oal="1.228 in"))
    assert r.v0_ms == pytest.approx(348.0, abs=0.1)
    assert r.pmax_bar == pytest.approx(903.9, abs=0.5)
    assert r.lauflaenge_mm == pytest.approx(127.0) and r.oal_mm == pytest.approx(31.19, abs=0.01)


def test_invalid_und_unbekannte_einheit():
    assert grt.parse(_roh(results__MuzzleVelocity="invalid")).v0_ms is None
    with pytest.raises(ValueError, match="Einheit"):
        grt.parse(_roh(results__MuzzleVelocity="348 furlong/fortnight"))


@pytest.mark.parametrize("roh", [b"kein json", b"[]", b'{"results": {}}', b"{" + b" " * 600_000 + b"}"])
def test_kein_grt_export(roh):
    with pytest.raises(ValueError):
        grt.parse(roh)


def test_abweichungen_zur_laborierung():
    r = grt.parse(FIXTURE.read_bytes())
    passend = Laborierung(name="x", kaliber=".45 ACP", pulver="HP-38", ladung_gr=Decimal("5.5"),
                          geschoss_gewicht_gr=Decimal("200"), l6_mm=Decimal("31.2"), huelsenlaenge_mm=Decimal("22.65"))
    assert grt.abweichungen(r, passend) == []
    anders = Laborierung(name="y", kaliber="9mm Luger", pulver="N320", ladung_gr=Decimal("5.8"),
                         l6_mm=Decimal("30.5"), huelsenlaenge_mm=Decimal("22.69"))
    texte = " | ".join(grt.abweichungen(r, anders))
    for teil in ("Ladung: GRT 5,5 gr, Laborierung 5,8 gr", "L6", "Hülsenlänge", "Pulver", "Kaliber"):
        assert teil in texte


def test_abweichung_v0():
    r = grt.parse(FIXTURE.read_bytes())
    diff, prozent = grt.abweichung_v0(r, 250.0)
    assert diff == pytest.approx(-98.0) and prozent == pytest.approx(-28.16, abs=0.01)
    assert grt.abweichung_v0(None, 250.0) is None


def _lab(client, **kw):
    daten = {"name": "Serie 2", "kaliber": ".45 ACP", "status": "in_test", "pulver": "HP-38", "ladung_gr": "5,5",
             "geschoss_gewicht_gr": "200", "l6_mm": "31,2", "huelsenlaenge_mm": "22,69"} | kw
    resp = client.post("/laborierung/neu", data=daten)
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def _import(client, lab_id, roh=None):
    datei = (io.BytesIO(roh or FIXTURE.read_bytes()), "l.json")
    return client.post(f"/laborierung/{lab_id}/grt", data={"datei": datei},
                       content_type="multipart/form-data", follow_redirects=True)


def test_import_anzeige_und_vergleich(eingeloggt, session):
    lab_id = _lab(eingeloggt)
    html = _import(eingeloggt, lab_id).get_data(as_text=True)
    assert "GRT-Rechnung importiert" in html
    assert "Hülsenlänge: GRT 22,65 mm, Laborierung 22,69 mm" in html  # Plausibilitätsprüfung
    assert "nicht gemessen" in html and "348,0 m/s" in html and "609,6 mm" in html
    eingeloggt.post(f"/laborierung/{lab_id}/testserie", data={"datum": "2026-10-06", "v_einzelwerte": "248 250"})
    html = eingeloggt.get(f"/laborierung/{lab_id}").get_data(as_text=True)
    assert "GRT-Rechnung 348,0 m/s" in html and "−99,0 m/s" in html  # gemessen 249 vs. 348
    assert "Geschwindigkeit im Vergleich" in html and "stroke-dasharray" in html and "GRT 348" in html


def test_import_ersetzen_loeschen_und_duplizieren(eingeloggt, session):
    lab_id = _lab(eingeloggt)
    _import(eingeloggt, lab_id)
    html = _import(eingeloggt, lab_id, _roh(results__MuzzleVelocity="255.0 m/s")).get_data(as_text=True)
    assert "GRT-Rechnung ersetzt" in html
    assert grt.aus_json(session.get(Laborierung, lab_id).grt_rechnung).v0_ms == 255.0
    neu_id = int(eingeloggt.post(f"/laborierung/{lab_id}/duplizieren").headers["Location"].split("/")[-2])
    session.expire_all()
    assert session.get(Laborierung, neu_id).grt_rechnung is None  # passt nicht zur geänderten Kopie
    eingeloggt.post(f"/laborierung/{lab_id}/grt/loeschen")
    session.expire_all()
    assert session.get(Laborierung, lab_id).grt_rechnung is None


def test_import_fehlerhafte_datei(eingeloggt, session):
    lab_id = _lab(eingeloggt)
    html = _import(eingeloggt, lab_id, b"<xml/>").get_data(as_text=True)
    assert "GRT-Import fehlgeschlagen" in html
    assert session.get(Laborierung, lab_id).grt_rechnung is None


def test_backup_enthaelt_grt(eingeloggt, session):
    lab_id = _lab(eingeloggt)
    _import(eingeloggt, lab_id)
    daten = json.loads(eingeloggt.get("/backup/export.json").data)
    assert grt.aus_json(daten["laborierungen"][0]["grt_rechnung"]).v0_ms == 348.0
