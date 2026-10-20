"""Bind one proposal to each durable capture job, including crash recovery."""

import sqlalchemy as sa
from alembic import op

revision = "247ad90b771c"
down_revision = "8ee6a82ef8ff"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("proposals", sa.Column("source_job_id", sa.String(), nullable=True))
    op.create_index("ix_proposals_source_job_id", "proposals", ["source_job_id"], unique=True)


def downgrade():
    op.drop_index("ix_proposals_source_job_id", table_name="proposals")
    op.drop_column("proposals", "source_job_id")
