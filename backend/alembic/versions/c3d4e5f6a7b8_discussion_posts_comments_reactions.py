"""discussion: posts, comments, reactions, notifications

Revision ID: c3d4e5f6a7b8
Revises: 9a1b2c3d4e5f
Create Date: 2026-09-19 16:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "9a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("forum_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["forum_id"], ["forums.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_posts_author_id", "posts", ["author_id"], unique=False)
    op.create_index("ix_posts_created_at", "posts", ["created_at"], unique=False)
    op.create_index("ix_posts_forum_id", "posts", ["forum_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_author_id", "comments", ["author_id"], unique=False)
    op.create_index("ix_comments_created_at", "comments", ["created_at"], unique=False)
    op.create_index("ix_comments_post_id", "comments", ["post_id"], unique=False)

    op.create_table(
        "post_reactions",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "user_id"),
    )
    op.create_index("ix_post_reactions_post_id", "post_reactions", ["post_id"], unique=False)
    op.create_index("ix_post_reactions_user_id", "post_reactions", ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=True),
        sa.Column("forum_id", sa.Uuid(), nullable=True),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["forum_id"], ["forums.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_post_reactions_user_id", table_name="post_reactions")
    op.drop_index("ix_post_reactions_post_id", table_name="post_reactions")
    op.drop_table("post_reactions")
    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_index("ix_comments_created_at", table_name="comments")
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_posts_forum_id", table_name="posts")
    op.drop_index("ix_posts_created_at", table_name="posts")
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_table("posts")
