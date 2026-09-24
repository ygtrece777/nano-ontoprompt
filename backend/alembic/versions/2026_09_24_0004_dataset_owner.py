"""Record the owner of v2 datasets.

Revision ID: 0004_dataset_owner
Revises: 0003_entity_instances
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_dataset_owner"
down_revision = "0003_entity_instances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("v2_datasets") as batch_op:
        batch_op.add_column(sa.Column("created_by", sa.String(), nullable=True))
        batch_op.create_foreign_key("fk_v2_datasets_created_by", "users", ["created_by"], ["id"])
    op.create_index("ix_v2_datasets_created_by", "v2_datasets", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_v2_datasets_created_by", table_name="v2_datasets")
    with op.batch_alter_table("v2_datasets") as batch_op:
        batch_op.drop_constraint("fk_v2_datasets_created_by", type_="foreignkey")
        batch_op.drop_column("created_by")
