"""Hülsen-Verwendung je Los

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22 09:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("los", schema=None) as batch_op:
        batch_op.add_column(sa.Column("huelsen_verwendung", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("los", schema=None) as batch_op:
        batch_op.drop_column("huelsen_verwendung")
