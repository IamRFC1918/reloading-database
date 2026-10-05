"""Export/Import als JSON oder als ZIP mit drei CSV-Dateien.

Beide Formate gehen durch dieselbe Zwischenstruktur
`{"laborierungen": [{..., "testserien": [...], "lose": [...]}]}`.
Import legt immer NEUE Datensätze an (IDs werden neu vergeben); Lose,
deren Los-Nr. schon existiert, werden übersprungen. Fotos sind nicht
enthalten (nur ihre Pfade) – die liegen auf dem PVC und werden separat
gesichert.
"""
import csv
import io
import json
import zipfile
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from models import Foto, Laborierung, Los, Testserie
from storage import Session
from units import parse_date, parse_decimal, parse_int

FORMAT_VERSION = 1

LAB_SPALTEN = [c.key for c in Laborierung.__table__.columns if c.key not in ("erstellt_am", "geaendert_am")]
TEST_SPALTEN = [c.key for c in Testserie.__table__.columns if c.key != "erstellt_am"]
LOS_SPALTEN = [c.key for c in Los.__table__.columns if c.key != "erstellt_am"]


def _wert(value):
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _zeile(obj, spalten):
    return {k: _wert(getattr(obj, k)) for k in spalten}


def export_daten():
    labs = Session.scalars(select(Laborierung).order_by(Laborierung.id)).all()
    return {
        "format": "ladedaten",
        "version": FORMAT_VERSION,
        "exportiert_am": datetime.now().isoformat(timespec="seconds"),
        "laborierungen": [
            {
                **_zeile(lab, LAB_SPALTEN),
                "testserien": [
                    {**_zeile(t, TEST_SPALTEN), "fotos": [f.pfad for f in t.fotos]}
                    for t in lab.testserien
                ],
                "lose": [_zeile(los, LOS_SPALTEN) for los in lab.lose],
            }
            for lab in labs
        ],
    }


def export_json():
    return json.dumps(export_daten(), ensure_ascii=False, indent=2)


def _csv(model, spalten, zeilen):
    dezimal = {c.key for c in model.__table__.columns if c.type.python_type is Decimal}
    buf = io.StringIO()
    # Semikolon + Dezimalkomma, damit Excel/LibreOffice (de) es direkt öffnet
    writer = csv.DictWriter(buf, fieldnames=spalten, delimiter=";", extrasaction="ignore")
    writer.writeheader()
    for z in zeilen:
        writer.writerow({k: (v.replace(".", ",") if k in dezimal and v else v) for k, v in z.items()})
    return "\ufeff" + buf.getvalue()  # BOM für Excel


def export_csv_zip():
    daten = export_daten()["laborierungen"]
    tests = [t for lab in daten for t in lab["testserien"]]
    lose = [los for lab in daten for los in lab["lose"]]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("laborierungen.csv", _csv(Laborierung, LAB_SPALTEN, daten))
        zf.writestr("testserien.csv", _csv(Testserie, TEST_SPALTEN, tests))
        zf.writestr("lose.csv", _csv(Los, LOS_SPALTEN, lose))
    return buf.getvalue()


def _lies_csv(zf, name):
    if name not in zf.namelist():
        return []
    text = zf.read(name).decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def csv_zip_zu_daten(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        labs = _lies_csv(zf, "laborierungen.csv")
        tests = _lies_csv(zf, "testserien.csv")
        lose = _lies_csv(zf, "lose.csv")
    for lab in labs:
        lab["testserien"] = [t for t in tests if t.get("laborierung_id") == lab.get("id")]
        lab["lose"] = [los for los in lose if los.get("laborierung_id") == lab.get("id")]
    return {"laborierungen": labs}


def _konvertiere(model, zeile, ignorieren):
    """Strings/JSON-Werte -> passende Python-Typen anhand der Spaltentypen."""
    werte = {}
    for col in model.__table__.columns:
        if col.key in ignorieren or col.key not in zeile:
            continue
        raw = zeile[col.key]
        if raw == "":
            raw = None
        typ = col.type.python_type
        if raw is None:
            werte[col.key] = None
        elif typ is Decimal:
            werte[col.key] = parse_decimal(raw)
        elif typ is int:
            werte[col.key] = parse_int(raw)
        elif typ is bool:
            werte[col.key] = raw if isinstance(raw, bool) else str(raw).lower() in ("true", "1", "ja")
        elif typ is date:
            werte[col.key] = parse_date(raw)
        else:
            werte[col.key] = str(raw)
    return werte


def importiere(daten):
    """-> Statistik-Dict. Commit macht der Aufrufer."""
    if not isinstance(daten, dict) or not isinstance(daten.get("laborierungen"), list):
        raise ValueError("Unbekanntes Format: 'laborierungen' fehlt.")
    vorhandene_lose = set(Session.scalars(select(Los.los_nr)).all())
    stat = {"laborierungen": 0, "testserien": 0, "lose": 0, "lose_uebersprungen": 0}
    alt_zu_neu, vorgaenger = {}, []
    ignorieren = {"id", "laborierung_id", "vorgaenger_id"}

    for zeile in daten["laborierungen"]:
        lab = Laborierung(**_konvertiere(Laborierung, zeile, ignorieren))
        lab.status = lab.status or "entwurf"
        Session.add(lab)
        for t in zeile.get("testserien", []):
            serie = Testserie(**_konvertiere(Testserie, t, ignorieren))
            serie.fotos = [Foto(pfad=p) for p in t.get("fotos", []) if isinstance(p, str)]
            lab.testserien.append(serie)
            stat["testserien"] += 1
        for los_zeile in zeile.get("lose", []):
            if los_zeile.get("los_nr") in vorhandene_lose:
                stat["lose_uebersprungen"] += 1
                continue
            lab.lose.append(Los(**_konvertiere(Los, los_zeile, ignorieren)))
            vorhandene_lose.add(los_zeile.get("los_nr"))
            stat["lose"] += 1
        Session.flush()
        alt_zu_neu[str(zeile.get("id"))] = lab
        vorgaenger.append((lab, str(zeile.get("vorgaenger_id") or "")))
        stat["laborierungen"] += 1

    # Vorgänger-Verweise innerhalb des Imports neu verknüpfen
    for lab, alt_id in vorgaenger:
        if alt_id in alt_zu_neu:
            lab.vorgaenger_id = alt_zu_neu[alt_id].id
    return stat
