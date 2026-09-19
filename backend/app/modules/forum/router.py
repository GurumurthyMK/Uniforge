"""Forum API: class forums, proposals, reviews, membership + discussion."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.db.session import get_db
from app.modules.forum import schemas as fs
from app.modules.forum import service as fsvc
from app.modules.identity import models as im
from app.modules.identity.deps import get_current_user

router = APIRouter(tags=["forum"])


@router.get("/classes/{class_id}/forums", response_model=list[fs.ForumOut])
def list_class_forums(
    class_id: uuid.UUID,
    include_pending: bool = Query(default=False),
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> list[fs.ForumOut]:
    return fsvc.list_forums(db, caller, class_id, include_pending=include_pending)


@router.get("/classes/{class_id}/forums/proposals", response_model=list[fs.ForumOut])
def list_proposals(
    class_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> list[fs.ForumOut]:
    return fsvc.list_pending(db, caller, class_id)


@router.post("/classes/{class_id}/forums", response_model=fs.ForumOut, status_code=201)
def propose(
    class_id: uuid.UUID,
    data: fs.ForumCreateIn,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.ForumOut:
    return fsvc.propose_forum(db, caller, class_id, data)


@router.get("/forums/joined", response_model=list[fs.ForumOut])
def list_joined_forums(
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> list[fs.ForumOut]:
    return fsvc.list_joined(db, caller)


@router.get("/forums/{forum_id}", response_model=fs.ForumOut)
def get_forum(
    forum_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.ForumOut:
    return fsvc.get_forum(db, caller, forum_id)


@router.patch("/forums/{forum_id}/review", response_model=fs.ForumOut)
def review(
    forum_id: uuid.UUID,
    data: fs.ForumReviewIn,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.ForumOut:
    return fsvc.review_forum(db, caller, forum_id, data.status)


@router.post("/forums/{forum_id}/join", response_model=fs.ForumOut)
def join(
    forum_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.ForumOut:
    return fsvc.join_forum(db, caller, forum_id)


@router.delete("/forums/{forum_id}/members/me", status_code=204)
def leave(
    forum_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> None:
    fsvc.leave_forum(db, caller, forum_id)
    return None


@router.post("/forums/{forum_id}/leave", status_code=204)
def leave_via_post(
    forum_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> None:
    fsvc.leave_forum(db, caller, forum_id)
    return None


# ── Posts ──

@router.post("/forums/{forum_id}/posts", response_model=fs.PostOut, status_code=201)
def create_post(
    forum_id: uuid.UUID,
    data: fs.PostCreateIn,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.PostOut:
    return fsvc.create_post(db, caller, forum_id, data)


@router.get("/forums/{forum_id}/posts", response_model=fs.PostListOut)
def list_posts(
    forum_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.PostListOut:
    return fsvc.list_posts(db, caller, forum_id, limit, offset)


@router.get("/forums/{forum_id}/posts/{post_id}", response_model=fs.PostOut)
def get_post(
    forum_id: uuid.UUID,
    post_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.PostOut:
    return fsvc.get_post(db, caller, forum_id, post_id)


@router.delete("/forums/{forum_id}/posts/{post_id}", status_code=204)
def delete_post(
    forum_id: uuid.UUID,
    post_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> None:
    fsvc.delete_post(db, caller, forum_id, post_id)
    return None


# ── Comments ──

@router.post("/forums/{forum_id}/posts/{post_id}/comments", response_model=fs.CommentOut, status_code=201)
def create_comment(
    forum_id: uuid.UUID,
    post_id: uuid.UUID,
    data: fs.CommentCreateIn,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.CommentOut:
    return fsvc.create_comment(db, caller, forum_id, post_id, data)


@router.get("/forums/{forum_id}/posts/{post_id}/comments", response_model=fs.CommentListOut)
def list_comments(
    forum_id: uuid.UUID,
    post_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.CommentListOut:
    return fsvc.list_comments(db, caller, forum_id, post_id, limit, offset)


@router.delete("/forums/{forum_id}/posts/{post_id}/comments/{comment_id}", status_code=204)
def delete_comment(
    forum_id: uuid.UUID,
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> None:
    fsvc.delete_comment(db, caller, forum_id, post_id, comment_id)
    return None


# ── Reactions (LIKE) ──

@router.post("/forums/{forum_id}/posts/{post_id}/like", response_model=dict)
def like_post(
    forum_id: uuid.UUID,
    post_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> dict:
    return fsvc.like_post(db, caller, forum_id, post_id)


@router.delete("/forums/{forum_id}/posts/{post_id}/like", response_model=dict)
def unlike_post(
    forum_id: uuid.UUID,
    post_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> dict:
    return fsvc.unlike_post(db, caller, forum_id, post_id)


# ── Notifications ──

@router.get("/notifications", response_model=list[fs.NotificationOut])
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> list[fs.NotificationOut]:
    return fsvc.list_notifications(db, caller, limit, offset)


@router.patch("/notifications/{notification_id}/read", response_model=fs.NotificationOut)
def mark_read(
    notification_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> fs.NotificationOut:
    return fsvc.mark_notification_read(db, caller, notification_id)
