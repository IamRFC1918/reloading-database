import io
import json
from decimal import Decimal

from models import Laborierung, Los, Testserie

LAB = {
    "name": "Serie 2", "kaliber": ".45 ACP", "status": "in_test", "datum": "2026-10-05",
    "geschoss_hersteller": "L.O.S. Cerkno", "geschoss_gewicht_gr": "200", "geschoss_art": "SWC",
    "pulver": "HP-38", "ladung_gr": "5,5", "l6_mm": "31,2", "huelsenmund_mm": "11,99",
    "huelsenlaenge_mm": "22,69", "matrizen": "Hornady Custom Grade",
}


def _anlegen(client, **kw):
    resp = client.post("/laborierung/neu", data=LAB | kw)
    assert resp.status_code == 302, resp.get_data(as_text=True)
    return int(resp.headers["Location"].rstrip("/").split("/")[-1])


def test_laborierung_anlegen_mit_dezimalkomma(eingeloggt, session):
    lab_id = _anlegen(eingeloggt)
    lab = session.get(Laborierung, lab_id)
    assert lab.ladung_gr == Decimal("5.5") and lab.l6_mm == Decimal("31.2")
    html = eingeloggt.get(f"/laborierung/{lab_id}").get_data(as_text=True)
    assert "31,2 mm" in html and "5,5 gr" in html
    assert "Keine Quelle" in html


def test_ungueltige_zahl_zeigt_fehler(eingeloggt):
    resp = eingeloggt.post("/laborierung/neu", data=LAB | {"ladung_gr": "fünf"})
    assert resp.status_code == 422
    assert "keine gültige Zahl" in resp.get_data(as_text=True)


def test_warnung_ueber_max_ladung(eingeloggt):
    lab_id = _anlegen(eingeloggt, ladung_gr="6,0", max_ladung_gr="5,8", quelle="Ladetabelle X")
    html = eingeloggt.get(f"/laborierung/{lab_id}").get_data(as_text=True)
    assert "hinweis-warnung" in html and "über der Max-Ladung" in html
    assert "mit-warnung" in eingeloggt.get("/").get_data(as_text=True)


def test_filter(eingeloggt):
    _anlegen(eingeloggt, name="A", pulver="HP-38")
    _anlegen(eingeloggt, name="B", pulver="N320", status="verworfen")
    html = eingeloggt.get("/?pulver=N320").get_data(as_text=True)
    assert ">B<" in html and ">A<" not in html
    html = eingeloggt.get("/?status=in_test").get_data(as_text=True)
    assert ">A<" in html and ">B<" not in html


def test_duplizieren_und_vergleich(eingeloggt, session):
    lab_id = _anlegen(eingeloggt, l6_mm="30,5")
    resp = eingeloggt.post(f"/laborierung/{lab_id}/duplizieren")
    neu_id = int(resp.headers["Location"].split("/")[-2])
    eingeloggt.post(f"/laborierung/{neu_id}/bearbeiten", data=LAB | {"name": "Serie 3", "l6_mm": "31,2"})
    html = eingeloggt.get(f"/laborierung/{neu_id}").get_data(as_text=True)
    assert "Änderungen ggü. Vorserie" in html and "30,5 mm" in html
    # geänderte Parameter sind in der Schnellerfassung vorbelegt
    assert "L6 (Gesamtlänge) 30,5 mm → 31,2 mm" in html


def test_schnellerfassung_mit_foto(eingeloggt, session, app):
    lab_id = _anlegen(eingeloggt)
    resp = eingeloggt.post(f"/laborierung/{lab_id}/testserie", data={
        "datum": "2026-10-05", "waffe": "Colt Gold Cup", "stueckzahl": "50",
        "schlitten_schliesst": "nein", "anzahl_probleme": "3",
        "fotos": (io.BytesIO(b"\xff\xd8fakejpeg"), "scheibe.jpg"),
    }, content_type="multipart/form-data")
    assert resp.status_code == 302
    serie = session.query(Testserie).one()
    assert serie.schlitten_schliesst is False and serie.stueckzahl == 50
    foto = serie.fotos[0]
    assert (app.config["UPLOAD_DIR"] / foto.pfad).exists()
    assert eingeloggt.get(f"/fotos/{foto.pfad}").status_code == 200


def test_foto_falscher_typ_wird_abgelehnt(eingeloggt, session):
    lab_id = _anlegen(eingeloggt)
    eingeloggt.post(f"/laborierung/{lab_id}/testserie", data={
        "datum": "2026-10-05", "fotos": (io.BytesIO(b"x"), "boese.html"),
    }, content_type="multipart/form-data")
    assert session.query(Testserie).one().fotos == []


def test_los_und_etikett(eingeloggt, session):
    lab_id = _anlegen(eingeloggt)
    eingeloggt.post(f"/laborierung/{lab_id}/los", data={"anzahl": "100", "datum": "2026-10-05"})
    eingeloggt.post(f"/laborierung/{lab_id}/los", data={"anzahl": "50", "datum": "2026-10-06"})
    nummern = sorted(los.los_nr for los in session.query(Los))
    assert nummern == ["45ACP-2026-001", "45ACP-2026-002"]
    los = session.query(Los).filter_by(los_nr="45ACP-2026-001").one()

    html = eingeloggt.get(f"/los/{los.id}/etikett").get_data(as_text=True)
    assert "size: 90mm 60mm" in html and "45ACP-2026-001" in html and "<svg" in html
    assert "Hornady Custom Grade" in html and "31,2 mm" in html
    html = eingeloggt.get(f"/los/{los.id}/etikett?groesse=70x50&qr=0&bogen=1").get_data(as_text=True)
    assert "size: 210mm 297mm" in html and "<svg" not in html

    resp = eingeloggt.get(f"/los/{los.id}/etikett.pdf")
    assert resp.mimetype == "application/pdf" and resp.data.startswith(b"%PDF")
    assert eingeloggt.get(f"/los/{los.id}/etikett.pdf?bogen=1").data.startswith(b"%PDF")


def test_laborierung_mit_losen_nicht_loeschbar(eingeloggt, session):
    lab_id = _anlegen(eingeloggt)
    eingeloggt.post(f"/laborierung/{lab_id}/los", data={"anzahl": "100", "datum": "2026-10-05"})
    eingeloggt.post(f"/laborierung/{lab_id}/loeschen")
    assert session.get(Laborierung, lab_id) is not None


def test_export_import_json_roundtrip(eingeloggt, session):
    lab_id = _anlegen(eingeloggt)
    eingeloggt.post(f"/laborierung/{lab_id}/testserie", data={"datum": "2026-10-05", "waffe": "Gold Cup"})
    eingeloggt.post(f"/laborierung/{lab_id}/los", data={"anzahl": "100", "datum": "2026-10-05"})
    daten = json.loads(eingeloggt.get("/backup/export.json").data)
    assert daten["laborierungen"][0]["ladung_gr"] == "5.5"

    resp = eingeloggt.post("/backup/import", data={
        "datei": (io.BytesIO(json.dumps(daten).encode()), "backup.json"),
    }, content_type="multipart/form-data")
    assert resp.status_code == 302
    assert session.query(Laborierung).count() == 2
    assert session.query(Testserie).count() == 2
    assert session.query(Los).count() == 1  # Los-Nr. existiert schon -> übersprungen


def test_export_import_csv_roundtrip(eingeloggt, session):
    lab_id = _anlegen(eingeloggt, geschoss_durchmesser=".451")
    eingeloggt.post(f"/laborierung/{lab_id}/testserie", data={"datum": "2026-10-05", "schlitten_schliesst": "ja"})
    zip_bytes = eingeloggt.get("/backup/export-csv.zip").data
    eingeloggt.post("/backup/import", data={"datei": (io.BytesIO(zip_bytes), "backup.zip")},
                    content_type="multipart/form-data")
    labs = session.query(Laborierung).order_by(Laborierung.id).all()
    assert len(labs) == 2
    assert labs[1].ladung_gr == Decimal("5.5") and labs[1].geschoss_durchmesser == ".451"
    assert labs[1].testserien[0].schlitten_schliesst is True


def test_manifest_oeffentlich(client):
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200 and resp.json["short_name"] == "Ladedaten"
