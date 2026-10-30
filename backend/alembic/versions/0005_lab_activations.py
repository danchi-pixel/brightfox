"""Add parent-controlled textbook lesson activation; preserve every progress row."""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("lab_activations",
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("learner_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.String(80), nullable=False),
        sa.Column("lesson_id", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["family_id", "learner_id"], ["learners.family_id", "learners.id"],
            ondelete="CASCADE", name="fk_lab_activations_learner"),
        sa.PrimaryKeyConstraint("learner_id", "topic_id", "lesson_id"))


def downgrade():
    raise RuntimeError("Production migrations are additive only; restore a backup to roll back.")
