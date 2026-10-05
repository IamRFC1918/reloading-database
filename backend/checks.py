"""Hinweise und Warnungen zu einer Laborierung.

Das Tool gibt bewusst keine Ladedaten vor. Es vergleicht nur die eigenen
Angaben mit der eingetragenen Max-Ladung aus der Quelle.
"""
from dataclasses import dataclass

from forms import LABORIERUNG_FELDER, VERGLEICH_IGNORIERT
from units import fmt_decimal


@dataclass(frozen=True)
class Hinweis:
    stufe: str  # "warnung" (gelb) oder "info"
    text: str


def hinweise(lab):
    result = []
    if lab.ladung_gr is not None and lab.max_ladung_gr is not None and lab.ladung_gr > lab.max_ladung_gr:
        result.append(Hinweis(
            "warnung",
            f"Ladung {fmt_decimal(lab.ladung_gr)} gr liegt über der Max-Ladung laut Quelle "
            f"({fmt_decimal(lab.max_ladung_gr)} gr).",
        ))
    if not (lab.quelle or "").strip():
        result.append(Hinweis("info", "Keine Quelle für die Ladedaten angegeben."))
    elif lab.max_ladung_gr is None:
        result.append(Hinweis("info", "Max-Ladung laut Quelle ist nicht eingetragen."))
    return result


def hat_warnung(lab):
    return any(h.stufe == "warnung" for h in hinweise(lab))


def unterschiede(alt, neu):
    """Geänderte Ladeparameter als Liste von (Label, alt, neu), formatiert."""
    result = []
    for feld in LABORIERUNG_FELDER:
        if feld.name in VERGLEICH_IGNORIERT:
            continue
        a, b = getattr(alt, feld.name), getattr(neu, feld.name)
        if a != b:
            result.append((feld.label, feld.anzeige(a) or "–", feld.anzeige(b) or "–"))
    return result


def unterschiede_text(alt, neu):
    return "; ".join(f"{label} {a} → {b}" for label, a, b in unterschiede(alt, neu))
