"""Kleine Diagramme als Inline-SVG (serverseitig, ohne JS-Bibliothek, CSP-tauglich).

Farben aus der validierten Referenzpalette (dataviz): Slots 1–3 sind auch für
Punktdiagramme mit allen Paaren farbfehlsicht-tauglich. Mehr als drei
Laborierungen werden nicht gleichzeitig eingefärbt (siehe vergleich_diagramm).
Tooltips über <title>; die Werte stehen zusätzlich als Tabelle in der Seite.
"""
import math

from markupsafe import Markup, escape

from units import fmt_decimal

SERIEN_FARBEN = ("#2a78d6", "#eb6834", "#1baf7a")  # blau, orange, aqua
BAND = "#cde2fb"  # blau 100: Streuband ±SD
MITTEL = "#1c5cab"  # blau 550: Mittelwertlinie
GITTER = "#e3e6e9"
FLAECHE = "#ffffff"

B, H = 360, 200
RAND = {"l": 40, "r": 58, "o": 24, "u": 30}
MAX_VERGLEICH = 12


def _z(x):
    """Zahl mit Dezimalkomma, eine Nachkommastelle (ganzzahlig ohne)."""
    return fmt_decimal(round(x, 1))


def _skala(lo, hi, ticks=4):
    """Runde Achsenwerte, die lo..hi abdecken -> (start, ende, schritt)."""
    spanne = max(hi - lo, 4.0)
    roh = spanne / ticks
    stufe = 10 ** math.floor(math.log10(roh))
    schritt = next(s * stufe for s in (1, 2, 2.5, 5, 10) if s * stufe >= roh)
    return math.floor(lo / schritt) * schritt, math.ceil(hi / schritt) * schritt, schritt


def _rahmen(titel, lo, hi):
    """Gitter + y-Achse; liefert (svg-Teile, y-Funktion)."""
    y0, y1, schritt = _skala(lo, hi)
    oben, unten = RAND["o"], H - RAND["u"]

    def y(v):
        return unten - (v - y0) / (y1 - y0) * (unten - oben)

    teile = [
        f'<svg class="diagramm" viewBox="0 0 {B} {H}" role="img" aria-label="{escape(titel)}">',
        f"<title>{escape(titel)}</title>",
    ]
    v = y0
    while v <= y1 + schritt / 1000:
        teile.append(f'<line x1="{RAND["l"]}" x2="{B - RAND["r"]}" y1="{y(v):.1f}" y2="{y(v):.1f}" '
                     f'stroke="{GITTER}" stroke-width="1"/>')
        teile.append(f'<text x="{RAND["l"] - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{_z(v)}</text>')
        v += schritt
    # Einheit über der Achse, mit Abstand zum obersten Achsenwert
    teile.append(f'<text x="{RAND["l"] - 6}" y="{oben - 12}" text-anchor="end" class="einheit">m/s</text>')
    return teile, y


def schuss_diagramm(werte_ms, titel="Geschwindigkeit je Schuss"):
    """Einzelschüsse als Punkte, Mittelwert als Linie, ±1 SD als Band."""
    werte = [float(v) for v in werte_ms]
    if not werte:
        return Markup("")
    n = len(werte)
    mittel = sum(werte) / n
    sd = math.sqrt(sum((v - mittel) ** 2 for v in werte) / (n - 1)) if n >= 2 else 0.0
    teile, y = _rahmen(titel, min(min(werte), mittel - sd), max(max(werte), mittel + sd))
    links, rechts = RAND["l"] + 12, B - RAND["r"] - 12

    def x(i):
        return (links + rechts) / 2 if n == 1 else links + i * (rechts - links) / (n - 1)

    if sd:
        teile.append(f'<rect x="{RAND["l"]}" width="{B - RAND["l"] - RAND["r"]}" y="{y(mittel + sd):.1f}" '
                     f'height="{y(mittel - sd) - y(mittel + sd):.1f}" fill="{BAND}" opacity=".7">'
                     f"<title>±1 SD: {_z(mittel - sd)} – {_z(mittel + sd)} m/s</title></rect>")
    teile.append(f'<line x1="{RAND["l"]}" x2="{B - RAND["r"]}" y1="{y(mittel):.1f}" y2="{y(mittel):.1f}" '
                 f'stroke="{MITTEL}" stroke-width="2"/>')
    teile.append(f'<text x="{B - RAND["r"] + 4}" y="{y(mittel) + 4:.1f}" class="beschriftung">Ø {_z(mittel)}</text>')

    jede = 1 if n <= 12 else 5
    for i, v in enumerate(werte):
        if (i + 1) % jede == 0 or i == 0:
            teile.append(f'<text x="{x(i):.1f}" y="{H - 14}" text-anchor="middle">{i + 1}</text>')
        tipp = f"Schuss {i + 1}: {_z(v)} m/s ({_z(v / 0.3048)} fps)"
        teile.append(f'<g><title>{tipp}</title>'
                     f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="12" fill="transparent"/>'
                     f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="4.5" fill="{SERIEN_FARBEN[0]}" '
                     f'stroke="{FLAECHE}" stroke-width="2"/></g>')
    teile.append(f'<text x="{(links + rechts) / 2:.1f}" y="{H - 2}" text-anchor="middle" class="einheit">Schuss</text>')
    teile.append("</svg>")
    return Markup("".join(teile))


def vergleich_diagramm(eintraege, titel="Mittlere Geschwindigkeit je Testserie"):
    """Ø v0 je Testserie mit ±1 SD als Fehlerbalken, Farbe = Laborierung.

    eintraege: Liste von dicts mit label, gruppe (Index 0..2), mittel, sd (oder None), tipp.
    """
    eintraege = eintraege[-MAX_VERGLEICH:]
    if not eintraege:
        return Markup("")
    lo = min(e["mittel"] - (e["sd"] or 0) for e in eintraege)
    hi = max(e["mittel"] + (e["sd"] or 0) for e in eintraege)
    teile, y = _rahmen(titel, lo, hi)
    n = len(eintraege)
    breite = (B - RAND["l"] - RAND["r"]) / n
    for i, e in enumerate(eintraege):
        cx = RAND["l"] + breite * (i + 0.5)
        farbe = SERIEN_FARBEN[e["gruppe"] % len(SERIEN_FARBEN)]
        teile.append(f"<g><title>{escape(e['tipp'])}</title>")
        teile.append(f'<rect x="{cx - breite / 2:.1f}" y="{RAND["o"]}" width="{breite:.1f}" '
                     f'height="{H - RAND["o"] - RAND["u"]}" fill="transparent"/>')
        if e["sd"]:
            o, u = y(e["mittel"] + e["sd"]), y(e["mittel"] - e["sd"])
            teile.append(f'<line x1="{cx:.1f}" x2="{cx:.1f}" y1="{o:.1f}" y2="{u:.1f}" '
                         f'stroke="{farbe}" stroke-width="2" stroke-linecap="round"/>')
            for yy in (o, u):
                teile.append(f'<line x1="{cx - 5:.1f}" x2="{cx + 5:.1f}" y1="{yy:.1f}" y2="{yy:.1f}" '
                             f'stroke="{farbe}" stroke-width="2" stroke-linecap="round"/>')
        teile.append(f'<circle cx="{cx:.1f}" cy="{y(e["mittel"]):.1f}" r="5" fill="{farbe}" '
                     f'stroke="{FLAECHE}" stroke-width="2"/></g>')
        if n <= 8 or i % 2 == 0:
            teile.append(f'<text x="{cx:.1f}" y="{H - 14}" text-anchor="middle">{escape(e["label"])}</text>')
    teile.append("</svg>")
    return Markup("".join(teile))
