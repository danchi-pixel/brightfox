"""Add learning-bank progress. No existing table is altered or recreated."""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("lab_progress",
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.String(80), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["family_id", "learner_id"], ["learners.family_id", "learners.id"],
            ondelete="CASCADE", name="fk_lab_progress_learner"),
        sa.PrimaryKeyConstraint("learner_id", "topic_id"))


def downgrade():
    raise RuntimeError("Production migrations are additive only; restore a backup to roll back.")
