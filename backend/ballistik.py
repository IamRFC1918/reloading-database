"""Auswertung gemessener Geschossgeschwindigkeiten (Chronograph).

Bewusst nur Rechnungen auf MESSWERTEN: Statistik der v0, Mündungsenergie und
Power Factor. Keine vorhersagende Innenballistik (Gasdruck, v0 aus der Ladung)
– das wäre eine Ladedaten-Vorgabe, siehe CLAUDE.md.

Einzelwerte werden immer in m/s gespeichert, als Text "251.3 249 253.8"
(Leerzeichen getrennt, Punkt als Dezimaltrenner).
"""
import re
import statistics
from dataclasses import dataclass
from decimal import Decimal

from units import parse_decimal

FPS_PRO_MS = 1 / 0.3048  # 1 ft = 0,3048 m (exakt)
KG_PRO_GRAIN = 0.00006479891  # 1 gr = 64,79891 mg (exakt)
EINHEITEN = (("ms", "m/s"), ("fps", "fps"))
MAX_WERTE = 100


def parse_messreihe(text, einheit="ms"):
    """'251,3 249\\n253.8' -> [Decimal('251.3'), ...] in m/s.
    Trenner: Leerzeichen, Zeilenumbruch, Semikolon, Tab. Komma oder Punkt = Dezimal."""
    teile = [t for t in re.split(r"[\s;]+", (text or "").strip()) if t]
    if len(teile) > MAX_WERTE:
        raise ValueError(f"höchstens {MAX_WERTE} Werte")
    werte = []
    for teil in teile:
        v = parse_decimal(teil)
        if v is None or v <= 0:
            raise ValueError(f"„{teil}“ ist keine gültige Geschwindigkeit")
        if einheit == "fps":
            v = (v * Decimal("0.3048")).quantize(Decimal("0.1"))
        if v > 2000:
            raise ValueError(f"„{teil}“ ist unplausibel hoch – Einheit prüfen")
        werte.append(v)
    return werte


def als_text(werte):
    """Speicherformat: 'Decimal-Liste' -> '251.3 249 253.8' (None bei leer)."""
    return " ".join(format(v.normalize(), "f") for v in werte) or None


def aus_text(text):
    return [Decimal(t) for t in (text or "").split()]


@dataclass(frozen=True)
class Statistik:
    n: int
    mittel: float
    minimum: float
    maximum: float
    sd: float | None  # Stichproben-Standardabweichung, erst ab 2 Werten

    @property
    def es(self):
        """Extreme Spread: größter minus kleinster Wert."""
        return self.maximum - self.minimum

    @property
    def cv(self):
        """Variationskoeffizient in %."""
        return self.sd / self.mittel * 100 if self.sd is not None and self.mittel else None


def statistik(werte):
    if not werte:
        return None
    f = [float(v) for v in werte]
    return Statistik(
        n=len(f),
        mittel=statistics.fmean(f),
        minimum=min(f),
        maximum=max(f),
        sd=statistics.stdev(f) if len(f) >= 2 else None,
    )


def fps(v_ms):
    return v_ms * FPS_PRO_MS


def energie_j(gewicht_gr, v_ms):
    """Mündungsenergie E0 = m·v²/2 in Joule."""
    return 0.5 * float(gewicht_gr) * KG_PRO_GRAIN * v_ms**2


def power_factor(gewicht_gr, v_ms):
    """Power Factor = Geschossgewicht (gr) × v (fps) / 1000."""
    return float(gewicht_gr) * fps(v_ms) / 1000


@dataclass(frozen=True)
class Auswertung:
    stat: Statistik
    einzelwerte: bool  # False: nur ein manuell eingetragener Mittelwert
    energie_j: float | None
    power_factor: float | None


def auswerten(serie):
    """Auswertung einer Testserie; None, wenn keine Geschwindigkeit erfasst ist."""
    werte = aus_text(serie.v_einzelwerte)
    einzeln = bool(werte)
    if not werte and serie.geschwindigkeit_ms is not None:
        werte = [serie.geschwindigkeit_ms]
    stat = statistik(werte)
    if stat is None:
        return None
    gewicht = serie.laborierung.geschoss_gewicht_gr if serie.laborierung else None
    return Auswertung(
        stat=stat,
        einzelwerte=einzeln,
        energie_j=energie_j(gewicht, stat.mittel) if gewicht else None,
        power_factor=power_factor(gewicht, stat.mittel) if gewicht else None,
    )
