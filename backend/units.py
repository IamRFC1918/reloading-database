"""Zahlen und Datum im deutschen Format: Eingabe mit Komma oder Punkt,
Ausgabe immer mit Dezimalkomma."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def parse_decimal(text):
    """'5,5' / '5.5' / ' 5,50 gr' -> Decimal('5.5'); leer -> None; Unsinn -> ValueError."""
    if text is None:
        return None
    if isinstance(text, (int, float, Decimal)):
        return Decimal(str(text))
    s = str(text).strip().lower()
    for suffix in ("gr", "mm", "m/s"):
        s = s.removesuffix(suffix).strip()
    if not s:
        return None
    s = s.replace(" ", "")
    # "1.234,5" -> "1234.5"; "5,5" -> "5.5"
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        value = Decimal(s)
    except InvalidOperation:
        raise ValueError(f"„{text}“ ist keine gültige Zahl") from None
    if not value.is_finite():
        raise ValueError(f"„{text}“ ist keine gültige Zahl")
    return value


def parse_int(text):
    if text is None or str(text).strip() == "":
        return None
    try:
        return int(str(text).strip())
    except ValueError:
        raise ValueError(f"„{text}“ ist keine ganze Zahl") from None


def parse_date(text):
    """ISO (vom <input type=date>) oder TT.MM.JJJJ."""
    if text is None or str(text).strip() == "":
        return None
    if isinstance(text, date):
        return text
    s = str(text).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"„{text}“ ist kein gültiges Datum")


def fmt_decimal(value):
    """Decimal('31.200') -> '31,2'; None -> ''. Nachkommanullen entfallen."""
    if value is None or value == "":
        return ""
    d = Decimal(str(value)).normalize()
    return format(d, "f").replace(".", ",")


def fmt_zahl(value, stellen=1, vorzeichen=False):
    """Gerundete Zahl mit Dezimalkomma: fmt_zahl(251.333) -> '251,3'; None -> ''."""
    if value is None:
        return ""
    text = f"{float(value):{'+' if vorzeichen else ''}.{stellen}f}".replace(".", ",")
    return text.replace("-", "−")


def fmt_date(value):
    return value.strftime("%d.%m.%Y") if value else ""
