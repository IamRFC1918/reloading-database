"""Etiketten für Lose: gemeinsame Daten für HTML-Druckansicht und PDF."""
import io
import re

import qrcode
import qrcode.image.svg
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from units import fmt_date, fmt_decimal

MIN_MM, MAX_MM = 30, 200
BOGEN_RAND_MM = 8


def parse_size(text, default="90x60"):
    """'90x60' -> (90, 60); ungültig oder außerhalb 30..200 mm -> default."""
    for candidate in (text, default):
        m = re.fullmatch(r"\s*(\d{2,3})\s*[xX×]\s*(\d{2,3})\s*", candidate or "")
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            if MIN_MM <= w <= MAX_MM and MIN_MM <= h <= MAX_MM:
                return w, h
    return 90, 60


def bogen_raster(breite, hoehe):
    """Wie viele Etiketten passen auf A4 (Spalten, Zeilen)?"""
    cols = int((210 - 2 * BOGEN_RAND_MM) // breite)
    rows = int((297 - 2 * BOGEN_RAND_MM) // hoehe)
    return max(cols, 1), max(rows, 1)


def _mit(value, einheit):
    text = fmt_decimal(value)
    return f"{text} {einheit}" if text else ""


def etikett_daten(los):
    """Zeilen (Label, Wert) fürs Etikett; leere Werte bleiben als Strich stehen,
    damit man sie bei Bedarf von Hand nachtragen kann."""
    lab = los.laborierung
    geschoss = " ".join(
        x for x in (lab.geschoss_hersteller, lab.geschoss_modell,
                    _mit(lab.geschoss_gewicht_gr, "gr"), lab.geschoss_art) if x
    )
    pulver = " ".join(x for x in (lab.pulver, _mit(lab.ladung_gr, "gr")) if x)
    return {
        "kaliber": lab.kaliber,
        "los_nr": los.los_nr,
        "zeilen": [
            ("Geschoss", geschoss or "–"),
            ("Pulver", pulver or "–"),
            ("L6", _mit(lab.l6_mm, "mm") or "–"),
            ("Hülsenmund", _mit(lab.huelsenmund_mm, "mm") or "–"),
            ("Hülsenlänge", _mit(lab.huelsenlaenge_mm, "mm") or "–"),
            ("Matrizen", lab.matrizen or "–"),
            ("Zündhütchen", lab.zuendhuetchen or "–"),
        ],
        "datum": fmt_date(los.datum),
        "anzahl": los.anzahl,
        "notiz": los.notiz or "",
    }


def qr_svg(url):
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=1)
    return img.to_string(encoding="unicode")


def _qr_png(url):
    buf = io.BytesIO()
    qrcode.make(url, border=1).save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _pdf_text(text):
    """Standardschriften können nur cp1252 – Emojis o. Ä. weglassen."""
    return str(text).encode("cp1252", "ignore").decode("cp1252").strip()


def _passend(c, text, font, size, max_breite):
    """Schrift so weit verkleinern, bis der Text in die Breite passt."""
    while size > 4 and c.stringWidth(text, font, size) > max_breite:
        size -= 0.25
    return size


def _zeichne_etikett(c, x, y, w, h, daten, qr):
    """Ein Etikett mit Ursprung unten links (x, y), alle Maße in Punkt."""
    pad = 2.5 * mm
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(0.5)
    c.rect(x, y, w, h)

    skala = h / (60 * mm)
    gross, klein = 12 * skala, 8 * skala
    qr_size = min(h * 0.38, w * 0.3) if qr else 0
    links, oben = x + pad, y + h - pad
    breite = w - 2 * pad

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", gross)
    c.drawString(links, oben - gross, _pdf_text(daten["kaliber"]))
    size = _passend(c, daten["los_nr"], "Helvetica-Bold", gross * 0.85, breite / 2)
    c.setFont("Helvetica-Bold", size)
    c.drawRightString(x + w - pad, oben - gross, daten["los_nr"])

    zeile_y = oben - gross - 1.6 * klein
    label_breite = 17 * mm * skala
    for i, (label, wert) in enumerate(daten["zeilen"]):
        wert = _pdf_text(wert)
        rechts_frei = breite - label_breite - (qr_size + pad if i < 4 and qr else 0)
        c.setFont("Helvetica", klein * 0.9)
        c.drawString(links, zeile_y, label)
        c.setFont("Helvetica-Bold", _passend(c, wert, "Helvetica-Bold", klein, rechts_frei))
        c.drawString(links + label_breite, zeile_y, wert)
        zeile_y -= klein * 1.35

    if qr:
        c.drawImage(qr, x + w - pad - qr_size, oben - gross - 0.8 * klein - qr_size,
                    qr_size, qr_size)

    # Fußzeilen am unteren Rand, damit die Notizzeile Platz zum Schreiben hat
    zeile_y = y + pad + 0.3 * klein
    c.setFont("Helvetica", klein)
    c.drawString(links, zeile_y, "Notiz:")
    notiz = _pdf_text(daten["notiz"])
    if notiz:
        c.setFont("Helvetica", _passend(c, notiz, "Helvetica", klein, breite - 12 * mm * skala))
        c.drawString(links + 10 * mm * skala, zeile_y, notiz)
    else:
        c.line(links + 10 * mm * skala, zeile_y - 1, x + w - pad, zeile_y - 1)
    zeile_y += klein * 1.6
    c.setFont("Helvetica", klein)
    c.drawString(links, zeile_y, f"Datum: {daten['datum']}")
    c.drawRightString(x + w - pad, zeile_y, f"Anzahl: {daten['anzahl']}")


def etikett_pdf(los, breite_mm=90, hoehe_mm=60, qr_url=None, bogen=False):
    """PDF mit einem Etikett pro Seite (Seitengröße = Etikett) oder einem
    vollen A4-Bogen mit so vielen Etiketten wie draufpassen."""
    daten = etikett_daten(los)
    qr = _qr_png(qr_url) if qr_url else None
    w, h = breite_mm * mm, hoehe_mm * mm
    buf = io.BytesIO()
    if bogen:
        c = canvas.Canvas(buf, pagesize=A4)
        cols, rows = bogen_raster(breite_mm, hoehe_mm)
        for row in range(rows):
            for col in range(cols):
                x = BOGEN_RAND_MM * mm + col * w
                y = A4[1] - BOGEN_RAND_MM * mm - (row + 1) * h
                _zeichne_etikett(c, x, y, w, h, daten, qr)
    else:
        c = canvas.Canvas(buf, pagesize=(w, h))
        _zeichne_etikett(c, 0, 0, w, h, daten, qr)
    c.setTitle(f"Etikett {los.los_nr}")
    c.showPage()
    c.save()
    return buf.getvalue()
