"""forum foundation: forums, memberships

Revision ID: 9a1b2c3d4e5f
Revises: 054f6af45a96
Create Date: 2026-09-19 15:00:00

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "9a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "054f6af45a96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forums",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("class_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="forumstatus", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_forums_class_id", "forums", ["class_id"], unique=False)
    op.create_index("ix_forums_created_by", "forums", ["created_by"], unique=False)
    op.create_index("ix_forums_status", "forums", ["status"], unique=False)
    op.create_index("uq_forums_class_name", "forums", ["class_id", "name"], unique=True)

    op.create_table(
        "forum_memberships",
        sa.Column("forum_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["forum_id"], ["forums.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("forum_id", "user_id"),
    )
    op.create_index("ix_forum_memberships_forum_id", "forum_memberships", ["forum_id"], unique=False)
    op.create_index("ix_forum_memberships_user_id", "forum_memberships", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_forum_memberships_user_id", table_name="forum_memberships")
    op.drop_index("ix_forum_memberships_forum_id", table_name="forum_memberships")
    op.drop_table("forum_memberships")
    op.drop_index("uq_forums_class_name", table_name="forums")
    op.drop_index("ix_forums_status", table_name="forums")
    op.drop_index("ix_forums_created_by", table_name="forums")
    op.drop_index("ix_forums_class_id", table_name="forums")
    op.drop_table("forums")
