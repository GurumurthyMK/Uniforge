"""connections: student network edges

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-19 17:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requester_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "ACCEPTED", "REJECTED", name="connectionstatus", native_enum=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("requester_id != recipient_id", name="ck_connections_no_self"),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connections_recipient_id", "connections", ["recipient_id"], unique=False)
    op.create_index("ix_connections_requester_id", "connections", ["requester_id"], unique=False)
    op.create_index("ix_connections_status", "connections", ["status"], unique=False)
    op.create_index("uq_connections_pair", "connections", ["requester_id", "recipient_id"], unique=True)
    op.create_index("ix_connections_pair_status", "connections", ["requester_id", "recipient_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_connections_pair_status", table_name="connections")
    op.drop_index("uq_connections_pair", table_name="connections")
    op.drop_index("ix_connections_status", table_name="connections")
    op.drop_index("ix_connections_requester_id", table_name="connections")
    op.drop_index("ix_connections_recipient_id", table_name="connections")
    op.drop_table("connections")
    # enum type cleanup is handled by SQLAlchemy native_enum=False - no separate type to drop
