"""create entity instance rows for pipeline mappings

Revision ID: 0003_entity_instances
Revises: 0002_entity_identifiers
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_entity_instances"
down_revision = "0002_entity_identifiers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "entity_instances" in inspector.get_table_names():
        return

    op.create_table(
        "entity_instances",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=False),
        sa.Column("ontology_id", sa.String(), nullable=False),
        sa.Column("row_identity", sa.String(length=200), nullable=False),
        sa.Column("row_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ontology_id"], ["ontology_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_entity_instances_row_identity",
        "entity_instances",
        ["row_identity"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_entity_instances_row_identity", table_name="entity_instances")
    op.drop_table("entity_instances")
