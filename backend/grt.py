"""Import einer einzelnen Ladung aus Gordons Reloading Tool (GRT, JSON-Export
"aktive Ladung").

Die Werte sind die RECHNUNG von GRT, keine Messung und keine Vorgabe dieses
Tools. Sie werden gespeichert, angezeigt und mit den gemessenen v0 verglichen.

GRT schreibt alle Werte als Text mit Einheit ("348.0 m/s", "609.60 mm") und
Namen URL-kodiert (".45%20Auto"). Je nach GRT-Einstellung können die
Einheiten abweichen; sie werden hier in m/s, bar, mm, gr und J umgerechnet.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote

# Faktor auf die Zieleinheit je Größe
UMRECHNUNG = {
    "geschwindigkeit": {"m/s": 1, "ft/s": 0.3048, "fps": 0.3048},
    "druck": {"bar": 1, "psi": 0.0689476, "mpa": 10, "kpa": 0.01},
    "laenge": {"mm": 1, "in": 25.4, "inch": 25.4, "cm": 10},
    "masse": {"grain": 1, "gr": 1, "g": 15.4323584},
    "energie": {"j": 1, "ft-lbs": 1.35582, "ftlbs": 1.35582, "ft·lbs": 1.35582},
    "zeit": {"ms": 1},
    "prozent": {"%": 1},
    "temperatur": {"°c": 1},
    "zahl": {},  # einheitenlose Kennzahlen (z. B. IPSC-Faktor)
}
MAX_DATEI = 512 * 1024


@dataclass
class Rechnung:
    importiert_am: str
    dateiname: str
    kaliber: str
    geschoss: str
    pulver: str
    ladung_gr: float | None
    geschoss_gewicht_gr: float | None
    oal_mm: float | None
    huelsenlaenge_mm: float | None
    lauflaenge_mm: float | None
    pulvertemp_c: float | None
    v0_ms: float | None
    pmax_bar: float | None
    pmax_zul_bar: float | None  # zulässiger Gasdruck laut Kaliberdaten in GRT (z. B. CIP)
    muendungsdruck_bar: float | None
    e0_j: float | None
    fuellgrad_pct: float | None
    abbrand_pct: float | None
    laufzeit_ms: float | None
    ipsc_factor: float | None
    meldungen: list = field(default_factory=list)  # Fehler/Warnungen aus GRT selbst


def _text(value):
    return unquote(str(value or "")).strip()


def _wert(value, groesse):
    """'348.0 m/s' -> 348.0 (in Zieleinheit); leer/'invalid' -> None."""
    s = _text(value)
    m = re.fullmatch(r"(-?\d+(?:[.,]\d+)?)\s*(.*)", s)
    if not m:
        return None
    zahl = float(m.group(1).replace(",", "."))
    einheit = m.group(2).strip().lower()
    # "grain H2O" (Hülsenvolumen) ist keine Masse – hier nicht verwendet
    if not einheit:
        return zahl
    faktor = UMRECHNUNG[groesse].get(einheit)
    if faktor is None:
        raise ValueError(f"unbekannte Einheit „{m.group(2)}“")
    return zahl * faktor


def parse(raw, dateiname=""):
    """Bytes/Text einer GRT-JSON-Datei -> Rechnung. ValueError bei Unsinn."""
    if isinstance(raw, bytes):
        if len(raw) > MAX_DATEI:
            raise ValueError("Datei zu groß für einen GRT-Export einer Ladung")
        raw = raw.decode("utf-8-sig", errors="replace")
    try:
        daten = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"keine gültige JSON-Datei ({exc.msg}, Zeile {exc.lineno})") from None
    if not isinstance(daten, dict) or not isinstance(daten.get("results"), dict) or "charge" not in daten:
        raise ValueError("kein GRT-Export einer Ladung („results“/„charge“ fehlen)")

    def teil(name):
        value = daten.get(name)
        return value if isinstance(value, dict) else {}

    cal, gun, proj, prop, res = (teil(n) for n in ("caliber", "gun", "projectile", "propellant", "results"))
    spec = teil("caliberspec")
    meldungen = []
    for art in ("errors", "warnings"):
        eintraege = teil("messages").get(art) or {}
        werte = eintraege.values() if isinstance(eintraege, dict) else eintraege
        meldungen += [f"GRT-{'Fehler' if art == 'errors' else 'Warnung'}: {_text(m)}" for m in werte]

    return Rechnung(
        importiert_am=datetime.now().isoformat(timespec="seconds"),
        dateiname=dateiname[:200],
        kaliber=_text(spec.get("altname")) or _text(cal.get("CaliberName")),
        geschoss=_text(proj.get("BulletName")),
        pulver=" ".join(x for x in (_text(prop.get("mname")), _text(prop.get("pname"))) if x),
        ladung_gr=_wert(daten.get("charge"), "masse"),
        geschoss_gewicht_gr=_wert(proj.get("mp"), "masse"),
        oal_mm=_wert(cal.get("oal"), "laenge"),
        huelsenlaenge_mm=_wert(cal.get("caselen"), "laenge"),
        lauflaenge_mm=_wert(gun.get("xe"), "laenge"),
        pulvertemp_c=_wert(prop.get("pt"), "temperatur"),
        v0_ms=_wert(res.get("MuzzleVelocity"), "geschwindigkeit"),
        pmax_bar=_wert(res.get("PeakPressure"), "druck"),
        pmax_zul_bar=_wert(cal.get("pMaxZul") or spec.get("Pmax"), "druck"),
        muendungsdruck_bar=_wert(res.get("MuzzlePressure"), "druck"),
        e0_j=_wert(res.get("MuzzleEnergy"), "energie"),
        fuellgrad_pct=_wert(res.get("LoadRatio"), "prozent"),
        abbrand_pct=_wert(res.get("BurnRatio"), "prozent"),
        laufzeit_ms=_wert(res.get("BarrelTime"), "zeit"),
        ipsc_factor=_wert(res.get("IPSCFactor"), "zahl"),
        meldungen=meldungen,
    )


def als_json(rechnung):
    """Speicherformat in laborierung.grt_rechnung (nur ausgewertete Felder,
    kein lokaler Dateipfad aus dem GRT-Export)."""
    return json.dumps(rechnung.__dict__, ensure_ascii=False)


def aus_json(text):
    if not text:
        return None
    try:
        return Rechnung(**json.loads(text))
    except (json.JSONDecodeError, TypeError):
        return None


def _normalisiert(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def abweichungen(rechnung, lab):
    """Unterschiede zwischen GRT-Eingaben und der Laborierung (Liste von Texten)."""
    hinweise = []

    def vergleiche(label, grt_wert, lab_wert, toleranz, einheit):
        if grt_wert is None or lab_wert is None:
            return
        if abs(grt_wert - float(lab_wert)) > toleranz:
            hinweise.append(f"{label}: GRT {_fmt(grt_wert)} {einheit}, Laborierung {_fmt(float(lab_wert))} {einheit}")

    vergleiche("Ladung", rechnung.ladung_gr, lab.ladung_gr, 0.005, "gr")
    vergleiche("Geschossgewicht", rechnung.geschoss_gewicht_gr, lab.geschoss_gewicht_gr, 0.05, "gr")
    vergleiche("L6", rechnung.oal_mm, lab.l6_mm, 0.02, "mm")
    vergleiche("Hülsenlänge", rechnung.huelsenlaenge_mm, lab.huelsenlaenge_mm, 0.02, "mm")
    if lab.pulver and rechnung.pulver and _normalisiert(lab.pulver) not in _normalisiert(rechnung.pulver):
        hinweise.append(f"Pulver: GRT „{rechnung.pulver}“, Laborierung „{lab.pulver}“")
    kal_lab = _normalisiert(lab.kaliber).replace("acp", "").replace("auto", "")
    kal_grt = _normalisiert(rechnung.kaliber).replace("acp", "").replace("auto", "")
    if kal_lab and kal_grt and kal_lab not in kal_grt and kal_grt not in kal_lab:
        hinweise.append(f"Kaliber: GRT „{rechnung.kaliber}“, Laborierung „{lab.kaliber}“")
    return hinweise


def abweichung_v0(rechnung, gemessen_ms):
    """(Differenz m/s, Differenz %) gemessen minus GRT, oder None."""
    if not rechnung or rechnung.v0_ms is None or gemessen_ms is None:
        return None
    diff = gemessen_ms - rechnung.v0_ms
    return diff, diff / rechnung.v0_ms * 100


def _fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")

