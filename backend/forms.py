"""Felddefinitionen für Formulare, Parsing, Vergleich und Export.

Eine Liste pro Entität statt WTForms-Klassen: Die Templates rendern die
Felder generisch, `parse_form` wandelt die Eingaben (Dezimalkomma!) in
Python-Werte. CSRF kommt global von Flask-WTF (CSRFProtect).
"""
from dataclasses import dataclass

from models import STATUS
from units import fmt_date, fmt_decimal, parse_date, parse_decimal, parse_int


@dataclass(frozen=True)
class Feld:
    name: str
    label: str
    typ: str = "text"  # text, textarea, dezimal, int, datum, select, janein
    gruppe: str = ""
    einheit: str = ""
    pflicht: bool = False
    auswahl: tuple = ()  # (wert, text) für select
    hilfe: str = ""

    def parse(self, raw):
        if self.typ == "dezimal":
            return parse_decimal(raw)
        if self.typ == "int":
            value = parse_int(raw)
            if value is not None and value < 0:
                raise ValueError("darf nicht negativ sein")
            return value
        if self.typ == "datum":
            return parse_date(raw)
        if self.typ == "janein":
            return {"ja": True, "nein": False}.get(str(raw or "").strip().lower())
        value = (raw or "").strip() if isinstance(raw, str) else raw
        if self.typ == "select" and value and value not in dict(self.auswahl):
            raise ValueError("ungültige Auswahl")
        return value or None

    def anzeige(self, value):
        """Formatierter Wert inkl. Einheit für Detailansicht/Etikett/Vergleich."""
        if value is None or value == "":
            return ""
        if self.typ == "dezimal":
            text = fmt_decimal(value)
        elif self.typ == "datum":
            text = fmt_date(value)
        elif self.typ == "janein":
            text = "ja" if value else "nein"
        elif self.typ == "select":
            text = dict(self.auswahl).get(value, value)
        else:
            text = str(value)
        return f"{text} {self.einheit}".strip()

    def formwert(self, value):
        """Wert für das value-Attribut im Eingabefeld."""
        if value is None:
            return ""
        if self.typ == "dezimal":
            return fmt_decimal(value)
        if self.typ == "datum":
            return value.isoformat()
        if self.typ == "janein":
            return "ja" if value else "nein"
        return str(value)


LABORIERUNG_FELDER = [
    Feld("name", "Name", gruppe="Allgemein", pflicht=True),
    Feld("kaliber", "Kaliber", gruppe="Allgemein", pflicht=True),
    Feld("status", "Status", "select", gruppe="Allgemein", auswahl=tuple(STATUS.items())),
    Feld("datum", "Datum", "datum", gruppe="Allgemein"),
    Feld("geschoss_hersteller", "Hersteller", gruppe="Geschoss"),
    Feld("geschoss_modell", "Modell", gruppe="Geschoss"),
    Feld("geschoss_gewicht_gr", "Gewicht", "dezimal", gruppe="Geschoss", einheit="gr"),
    Feld("geschoss_durchmesser", "Durchmesser", gruppe="Geschoss", hilfe="z. B. .451"),
    Feld("geschoss_art", "Art", gruppe="Geschoss", hilfe="z. B. SWC, RN, FMJ"),
    Feld("geschoss_oberflaeche", "Oberfläche", gruppe="Geschoss", hilfe="plattiert, blank, beschichtet"),
    Feld("pulver", "Pulver", gruppe="Ladung"),
    Feld("ladung_gr", "Ladung", "dezimal", gruppe="Ladung", einheit="gr"),
    Feld("zuendhuetchen", "Zündhütchen", gruppe="Ladung"),
    Feld("huelsenmarke", "Hülsenmarke", gruppe="Ladung"),
    Feld("l6_mm", "L6 (Gesamtlänge)", "dezimal", gruppe="Maße", einheit="mm"),
    Feld("huelsenlaenge_mm", "Hülsenlänge", "dezimal", gruppe="Maße", einheit="mm"),
    Feld("huelsenmund_mm", "Hülsenmund / Crimp", "dezimal", gruppe="Maße", einheit="mm"),
    Feld("matrizen", "Matrizen", gruppe="Maße"),
    Feld("quelle", "Quelle der Ladedaten", "textarea", gruppe="Quelle",
         hilfe="Ladetabelle, Handbuch, Link – das Tool gibt keine Ladedaten vor"),
    Feld("max_ladung_gr", "Max-Ladung laut Quelle", "dezimal", gruppe="Quelle", einheit="gr"),
    Feld("notiz", "Notiz", "textarea", gruppe="Quelle"),
]

TESTSERIE_FELDER = [
    Feld("datum", "Datum", "datum", pflicht=True),
    Feld("waffe", "Waffe"),
    Feld("federstaerke", "Federstärke", hilfe="z. B. 16 lbs"),
    Feld("stueckzahl", "Stückzahl", "int"),
    Feld("schlitten_schliesst", "Schlitten schließt", "janein"),
    Feld("anzahl_probleme", "Anzahl Probleme", "int"),
    Feld("ladehemmungen", "Ladehemmungen", "int"),
    Feld("streukreis_mm", "Streukreis", "dezimal", einheit="mm"),
    Feld("entfernung_m", "Entfernung", "int", einheit="m"),
    Feld("rueckstoss", "Rückstoß-Eindruck", "select",
         auswahl=(("weich", "weich"), ("mittel", "mittel"), ("hart", "hart"))),
    Feld("geschwindigkeit_ms", "Geschwindigkeit", "dezimal", einheit="m/s"),
    Feld("geaenderte_parameter", "Geänderte Parameter ggü. Vorserie", "textarea"),
    Feld("freitext", "Bemerkungen", "textarea"),
]

LOS_FELDER = [
    Feld("anzahl", "Anzahl", "int", pflicht=True),
    Feld("datum", "Datum", "datum", pflicht=True),
    Feld("notiz", "Notiz", "textarea"),
]

# Felder, die beim Vergleich mit dem Vorgänger nicht interessieren
VERGLEICH_IGNORIERT = {"name", "status", "datum", "notiz"}


def gruppiert(felder):
    gruppen = {}
    for feld in felder:
        gruppen.setdefault(feld.gruppe, []).append(feld)
    return gruppen


def parse_form(felder, form):
    """-> (werte, fehler) mit fehler = {feldname: meldung}."""
    werte, fehler = {}, {}
    for feld in felder:
        try:
            value = feld.parse(form.get(feld.name))
        except ValueError as exc:
            fehler[feld.name] = str(exc)
            continue
        if feld.pflicht and value in (None, ""):
            fehler[feld.name] = "Pflichtfeld"
            continue
        werte[feld.name] = value
    return werte, fehler
