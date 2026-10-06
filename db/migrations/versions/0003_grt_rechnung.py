"""GRT-Rechnung

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-06 21:18:22.904107
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("laborierung", schema=None) as batch_op:
        batch_op.add_column(sa.Column("grt_rechnung", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("laborierung", schema=None) as batch_op:
        batch_op.drop_column("grt_rechnung")
