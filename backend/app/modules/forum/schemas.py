"""Pydantic schemas for forum domain."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.forum.models import ForumStatus


class ForumCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class ForumReviewIn(BaseModel):
    status: ForumStatus

    model_config = ConfigDict(extra="forbid")


class ForumOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    class_id: uuid.UUID
    name: str
    description: str | None
    status: ForumStatus
    created_by: uuid.UUID | None
    approved_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    is_member: bool = False


class ForumDetailOut(ForumOut):
    pass


class MembershipOut(BaseModel):
    forum_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime


# Discussion

class PostCreateIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

    model_config = ConfigDict(extra="forbid")


class PostOut(BaseModel):
    id: uuid.UUID
    forum_id: uuid.UUID
    author_id: uuid.UUID | None
    author_display_name: str | None = None
    content: str
    created_at: datetime
    updated_at: datetime
    like_count: int = 0
    comment_count: int = 0
    liked_by_me: bool = False
    is_own: bool = False


class PostListOut(BaseModel):
    items: list[PostOut]
    total: int
    limit: int
    offset: int


class CommentCreateIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)

    model_config = ConfigDict(extra="forbid")


class CommentOut(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    author_id: uuid.UUID | None
    author_display_name: str | None = None
    content: str
    created_at: datetime
    updated_at: datetime
    is_own: bool = False


class CommentListOut(BaseModel):
    items: list[CommentOut]
    total: int
    limit: int
    offset: int


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    user_id: uuid.UUID
    actor_id: uuid.UUID | None
    type: str
    post_id: uuid.UUID | None
    forum_id: uuid.UUID | None
    comment_id: uuid.UUID | None
    message: str
    is_read: bool
    created_at: datetime
