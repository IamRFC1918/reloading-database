"""Datenbankzugriff: Engine/Session und die wenigen Abfragen, die mehr als
ein einfaches `session.get()` sind."""
import re
import time
from datetime import date

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import scoped_session, sessionmaker

from models import Laborierung, Los

Session = scoped_session(sessionmaker(expire_on_commit=False))

# Felder, die beim Duplizieren NICHT übernommen werden
_NICHT_KOPIEREN = {"id", "name", "status", "datum", "vorgaenger_id", "erstellt_am", "geaendert_am"}


def init_engine(url):
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)
    Session.configure(bind=engine)
    return engine


def wait_for_db(engine, seconds):
    """Beim Pod-Start ist die DB evtl. noch nicht bereit -> kurz warten."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if time.monotonic() > deadline:
                raise
            print("Datenbank noch nicht erreichbar, warte ...", flush=True)
            time.sleep(2)


def ping():
    Session.execute(text("SELECT 1"))


def laborierungen(kaliber=None, pulver=None, status=None, suche=None):
    stmt = select(Laborierung).order_by(Laborierung.datum.desc(), Laborierung.id.desc())
    if kaliber:
        stmt = stmt.where(Laborierung.kaliber == kaliber)
    if pulver:
        stmt = stmt.where(Laborierung.pulver == pulver)
    if status:
        stmt = stmt.where(Laborierung.status == status)
    if suche:
        stmt = stmt.where(Laborierung.name.contains(suche, autoescape=True))
    return Session.scalars(stmt).all()


def distinct_werte(spalte):
    """Vorhandene Werte z. B. für Filter-Auswahl und <datalist>-Vorschläge."""
    stmt = select(spalte).where(spalte.is_not(None), spalte != "").distinct().order_by(spalte)
    return Session.scalars(stmt).all()


def duplizieren(original):
    kopie = Laborierung(
        **{
            c.key: getattr(original, c.key)
            for c in Laborierung.__table__.columns
            if c.key not in _NICHT_KOPIEREN
        }
    )
    kopie.name = f"{original.name} (Kopie)"
    kopie.status = "entwurf"
    kopie.datum = date.today()
    kopie.vorgaenger_id = original.id
    Session.add(kopie)
    Session.flush()
    return kopie


def los_praefix(kaliber):
    """'.45 ACP' -> '45ACP'"""
    return re.sub(r"[^A-Z0-9]", "", (kaliber or "").upper()) or "LOS"


def naechste_los_nr(kaliber, jahr):
    """Fortlaufend je Kaliber und Jahr: 45ACP-2026-001, 45ACP-2026-002, ..."""
    prefix = f"{los_praefix(kaliber)}-{jahr}-"
    vorhandene = Session.scalars(select(Los.los_nr).where(Los.los_nr.startswith(prefix))).all()
    nummern = [int(nr[len(prefix):]) for nr in vorhandene if nr[len(prefix):].isdigit()]
    return f"{prefix}{max(nummern, default=0) + 1:03d}"


def anzahl_laborierungen():
    return Session.scalar(select(func.count(Laborierung.id)))
