"""ORM-Modelle (SQLAlchemy 2).

Alle Dezimalwerte sind `Numeric(7, 3)` und werden als `Decimal` gehalten:
Gewichte in grain (gr), Längen in mm. Das Schema muss mit
`db/migrations/versions/` übereinstimmen (Test: `alembic check`).
"""
from datetime import date, datetime
from decimal import Decimal

from flask_login import UserMixin
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

MARIADB_TABLE_ARGS = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

STATUS = {
    "entwurf": "Entwurf",
    "in_test": "in Test",
    "freigegeben": "freigegeben",
    "verworfen": "verworfen",
}

Dezimal = Numeric(7, 3)


class Base(DeclarativeBase):
    pass


class Benutzer(UserMixin, Base):
    __tablename__ = "benutzer"
    __table_args__ = MARIADB_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    passwort_hash: Mapped[str] = mapped_column(String(255))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Laborierung(Base):
    __tablename__ = "laborierung"
    __table_args__ = MARIADB_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kaliber: Mapped[str] = mapped_column(String(50), index=True)

    geschoss_hersteller: Mapped[str | None] = mapped_column(String(100))
    geschoss_modell: Mapped[str | None] = mapped_column(String(100))
    geschoss_gewicht_gr: Mapped[Decimal | None] = mapped_column(Dezimal)
    geschoss_durchmesser: Mapped[str | None] = mapped_column(String(20))  # z. B. ".451" oder "11,46 mm"
    geschoss_art: Mapped[str | None] = mapped_column(String(50))  # SWC, RN, FMJ ...
    geschoss_oberflaeche: Mapped[str | None] = mapped_column(String(50))  # plattiert, blank, beschichtet

    pulver: Mapped[str | None] = mapped_column(String(100), index=True)
    ladung_gr: Mapped[Decimal | None] = mapped_column(Dezimal)
    zuendhuetchen: Mapped[str | None] = mapped_column(String(100))
    huelsenmarke: Mapped[str | None] = mapped_column(String(100))

    l6_mm: Mapped[Decimal | None] = mapped_column(Dezimal)
    huelsenlaenge_mm: Mapped[Decimal | None] = mapped_column(Dezimal)
    huelsenmund_mm: Mapped[Decimal | None] = mapped_column(Dezimal)
    matrizen: Mapped[str | None] = mapped_column(String(200))

    quelle: Mapped[str | None] = mapped_column(Text)
    max_ladung_gr: Mapped[Decimal | None] = mapped_column(Dezimal)

    status: Mapped[str] = mapped_column(String(20), default="entwurf", index=True)
    datum: Mapped[date | None] = mapped_column(Date)
    notiz: Mapped[str | None] = mapped_column(Text)
    # Importierte Rechnung aus Gordons Reloading Tool (JSON, siehe grt.py)
    grt_rechnung: Mapped[str | None] = mapped_column(Text)

    # Gesetzt beim Duplizieren: Ausgangs-Laborierung der Vorserie
    vorgaenger_id: Mapped[int | None] = mapped_column(
        ForeignKey("laborierung.id", ondelete="SET NULL")
    )
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    vorgaenger: Mapped["Laborierung | None"] = relationship(remote_side=[id])
    testserien: Mapped[list["Testserie"]] = relationship(
        back_populates="laborierung",
        cascade="all, delete-orphan",
        order_by="(Testserie.datum.desc(), Testserie.id.desc())",
    )
    lose: Mapped[list["Los"]] = relationship(
        back_populates="laborierung", order_by="(Los.datum.desc(), Los.id.desc())"
    )

    @property
    def status_text(self):
        return STATUS.get(self.status, self.status)


class Testserie(Base):
    __tablename__ = "testserie"
    __table_args__ = MARIADB_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True)
    laborierung_id: Mapped[int] = mapped_column(
        ForeignKey("laborierung.id", ondelete="CASCADE"), index=True
    )
    datum: Mapped[date] = mapped_column(Date)
    waffe: Mapped[str | None] = mapped_column(String(100))
    federstaerke: Mapped[str | None] = mapped_column(String(50))
    stueckzahl: Mapped[int | None] = mapped_column(Integer)
    schlitten_schliesst: Mapped[bool | None] = mapped_column(Boolean)
    anzahl_probleme: Mapped[int | None] = mapped_column(Integer)
    ladehemmungen: Mapped[int | None] = mapped_column(Integer)
    streukreis_mm: Mapped[Decimal | None] = mapped_column(Dezimal)
    entfernung_m: Mapped[int | None] = mapped_column(Integer)
    rueckstoss: Mapped[str | None] = mapped_column(String(50))
    # Mittelwert; wird aus v_einzelwerte berechnet, wenn Einzelwerte erfasst sind
    geschwindigkeit_ms: Mapped[Decimal | None] = mapped_column(Dezimal)
    # Einzelschüsse vom Chronographen in m/s, Leerzeichen-getrennt (siehe ballistik.py)
    v_einzelwerte: Mapped[str | None] = mapped_column(Text)
    geaenderte_parameter: Mapped[str | None] = mapped_column(Text)
    freitext: Mapped[str | None] = mapped_column(Text)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    laborierung: Mapped[Laborierung] = relationship(back_populates="testserien")
    fotos: Mapped[list["Foto"]] = relationship(
        back_populates="testserie", cascade="all, delete-orphan", order_by="Foto.id"
    )


class Foto(Base):
    """Nur der Pfad relativ zu UPLOAD_DIR liegt in der DB, die Datei auf dem PVC."""

    __tablename__ = "foto"
    __table_args__ = MARIADB_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True)
    testserie_id: Mapped[int] = mapped_column(
        ForeignKey("testserie.id", ondelete="CASCADE"), index=True
    )
    pfad: Mapped[str] = mapped_column(String(255))
    originalname: Mapped[str | None] = mapped_column(String(255))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    testserie: Mapped[Testserie] = relationship(back_populates="fotos")


class Los(Base):
    __tablename__ = "los"
    __table_args__ = MARIADB_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT: geladene Patronen existieren physisch, die Laborierung darf
    # nicht verschwinden, solange es noch Lose dazu gibt.
    laborierung_id: Mapped[int] = mapped_column(
        ForeignKey("laborierung.id", ondelete="RESTRICT"), index=True
    )
    los_nr: Mapped[str] = mapped_column(String(50), unique=True)
    anzahl: Mapped[int] = mapped_column(Integer)
    datum: Mapped[date] = mapped_column(Date)
    notiz: Mapped[str | None] = mapped_column(Text)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    laborierung: Mapped[Laborierung] = relationship(back_populates="lose")

