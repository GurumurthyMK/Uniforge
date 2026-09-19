"""Forum domain models.

Forum lifecycle:
- A Forum belongs to exactly one Class.
- Status PENDING -> proposed by a class member, awaiting class rep review.
- APPROVED -> active, joinable by class members.
- REJECTED -> remains recorded but inactive.

Membership:
- ForumMembership links User <-> Forum, unique per pair.

Design notes:
- ForumProposal is represented by a Forum row with status=PENDING; no separate
  table is needed for minimal foundation. The name ForumProposal remains as a
  conceptual/schema artifact; the single table carries the proposal state.
- Foreign keys use SET NULL for user refs (created_by/approved_by) so user
  deletion does not cascade dangerously. Class FK uses CASCADE (deleting a
  class removes its forums, but deleting a forum never deletes the class).
- No ORM cascade from Forum to User/Class — deletion never spills.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ForumStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Forum(Base):
    __tablename__ = "forums"
    __table_args__ = (
        Index("ix_forums_class_id", "class_id"),
        Index("ix_forums_status", "status"),
        Index("ix_forums_created_by", "created_by"),
        Index("uq_forums_class_name", "class_id", "name", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ForumStatus] = mapped_column(
        Enum(ForumStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ForumStatus.PENDING,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ForumMembership(Base):
    """Student membership in an approved forum."""

    __tablename__ = "forum_memberships"
    __table_args__ = (
        Index("ix_forum_memberships_forum_id", "forum_id"),
        Index("ix_forum_memberships_user_id", "user_id"),
    )

    forum_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forums.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_forum_id", "forum_id"),
        Index("ix_posts_author_id", "author_id"),
        Index("ix_posts_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    forum_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("forums.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_post_id", "post_id"),
        Index("ix_comments_author_id", "author_id"),
        Index("ix_comments_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PostReaction(Base):
    """Single LIKE reaction per user per post."""

    __tablename__ = "post_reactions"
    __table_args__ = (
        Index("ix_post_reactions_post_id", "post_id"),
        Index("ix_post_reactions_user_id", "user_id"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. COMMENT_ON_POST
    post_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    forum_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("forums.id", ondelete="SET NULL"), nullable=True)
    comment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("comments.id", ondelete="SET NULL"), nullable=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Conceptual alias: a pending Forum IS a proposal. No additional table needed.
# If audit history is needed later, add forum_proposals table referencing Forum.
# For minimal foundation, the Forum table itself is the proposal record.
ForumProposal = Forum
