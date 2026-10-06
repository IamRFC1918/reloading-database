"""Einzelwerte Geschwindigkeit

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-06 20:56:20.945463
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("testserie", schema=None) as batch_op:
        batch_op.add_column(sa.Column("v_einzelwerte", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("testserie", schema=None) as batch_op:
        batch_op.drop_column("v_einzelwerte")
