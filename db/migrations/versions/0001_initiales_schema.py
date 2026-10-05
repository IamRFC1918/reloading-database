"""Initiales Schema

Revision ID: 0001
Revises: -
Create Date: 2026-10-05 14:52:26.312283
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "benutzer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("passwort_hash", sa.String(length=255), nullable=False),
        sa.Column("erstellt_am", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "laborierung",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kaliber", sa.String(length=50), nullable=False),
        sa.Column("geschoss_hersteller", sa.String(length=100), nullable=True),
        sa.Column("geschoss_modell", sa.String(length=100), nullable=True),
        sa.Column("geschoss_gewicht_gr", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("geschoss_durchmesser", sa.String(length=20), nullable=True),
        sa.Column("geschoss_art", sa.String(length=50), nullable=True),
        sa.Column("geschoss_oberflaeche", sa.String(length=50), nullable=True),
        sa.Column("pulver", sa.String(length=100), nullable=True),
        sa.Column("ladung_gr", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("zuendhuetchen", sa.String(length=100), nullable=True),
        sa.Column("huelsenmarke", sa.String(length=100), nullable=True),
        sa.Column("l6_mm", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("huelsenlaenge_mm", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("huelsenmund_mm", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("matrizen", sa.String(length=200), nullable=True),
        sa.Column("quelle", sa.Text(), nullable=True),
        sa.Column("max_ladung_gr", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("datum", sa.Date(), nullable=True),
        sa.Column("notiz", sa.Text(), nullable=True),
        sa.Column("vorgaenger_id", sa.Integer(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("geaendert_am", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["vorgaenger_id"], ["laborierung.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    with op.batch_alter_table("laborierung", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_laborierung_kaliber"), ["kaliber"], unique=False)
        batch_op.create_index(batch_op.f("ix_laborierung_pulver"), ["pulver"], unique=False)
        batch_op.create_index(batch_op.f("ix_laborierung_status"), ["status"], unique=False)

    op.create_table(
        "los",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("laborierung_id", sa.Integer(), nullable=False),
        sa.Column("los_nr", sa.String(length=50), nullable=False),
        sa.Column("anzahl", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("notiz", sa.Text(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["laborierung_id"], ["laborierung.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("los_nr"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    with op.batch_alter_table("los", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_los_laborierung_id"), ["laborierung_id"], unique=False)

    op.create_table(
        "testserie",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("laborierung_id", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("waffe", sa.String(length=100), nullable=True),
        sa.Column("federstaerke", sa.String(length=50), nullable=True),
        sa.Column("stueckzahl", sa.Integer(), nullable=True),
        sa.Column("schlitten_schliesst", sa.Boolean(), nullable=True),
        sa.Column("anzahl_probleme", sa.Integer(), nullable=True),
        sa.Column("ladehemmungen", sa.Integer(), nullable=True),
        sa.Column("streukreis_mm", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("entfernung_m", sa.Integer(), nullable=True),
        sa.Column("rueckstoss", sa.String(length=50), nullable=True),
        sa.Column("geschwindigkeit_ms", sa.Numeric(precision=7, scale=3), nullable=True),
        sa.Column("geaenderte_parameter", sa.Text(), nullable=True),
        sa.Column("freitext", sa.Text(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["laborierung_id"], ["laborierung.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    with op.batch_alter_table("testserie", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_testserie_laborierung_id"), ["laborierung_id"], unique=False)

    op.create_table(
        "foto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("testserie_id", sa.Integer(), nullable=False),
        sa.Column("pfad", sa.String(length=255), nullable=False),
        sa.Column("originalname", sa.String(length=255), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["testserie_id"], ["testserie.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    with op.batch_alter_table("foto", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_foto_testserie_id"), ["testserie_id"], unique=False)


def downgrade():
    with op.batch_alter_table("foto", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_foto_testserie_id"))

    op.drop_table("foto")
    with op.batch_alter_table("testserie", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_testserie_laborierung_id"))

    op.drop_table("testserie")
    with op.batch_alter_table("los", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_los_laborierung_id"))

    op.drop_table("los")
    with op.batch_alter_table("laborierung", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_laborierung_status"))
        batch_op.drop_index(batch_op.f("ix_laborierung_pulver"))
        batch_op.drop_index(batch_op.f("ix_laborierung_kaliber"))

    op.drop_table("laborierung")
    op.drop_table("benutzer")
