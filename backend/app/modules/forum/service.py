"""Forum service: proposal, review, membership, listing with strict class isolation."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.modules.forum import models as fm
from app.modules.forum import schemas as fs
from app.modules.identity import models as im
from app.modules.identity import service as isvc


def _verified_identity_for_class(user: im.User, class_id: uuid.UUID) -> im.UniversityIdentity | None:
    for ident in user.identities:
        if ident.status == im.IdentityStatus.VERIFIED and ident.class_id == class_id:
            return ident
    return None


def _is_class_rep_for(user: im.User, class_id: uuid.UUID) -> bool:
    for ident in user.identities:
        if (
            ident.status == im.IdentityStatus.VERIFIED
            and ident.class_id == class_id
            and ident.role == im.Role.CLASS_REP
        ):
            return True
    return False


def _require_class_member(user: im.User, class_id: uuid.UUID) -> im.UniversityIdentity:
    ident = _verified_identity_for_class(user, class_id)
    if ident is None:
        raise isvc.ForbiddenError("You are not a verified member of this class.")
    return ident


def _member_count(db: DbSession, forum_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(fm.ForumMembership).where(fm.ForumMembership.forum_id == forum_id)) or 0


def _is_member(db: DbSession, forum_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(fm.ForumMembership).where(
                fm.ForumMembership.forum_id == forum_id, fm.ForumMembership.user_id == user_id
            )
        )
        is not None
    )


def _to_out(db: DbSession, forum: fm.Forum, caller: im.User | None = None) -> fs.ForumOut:
    count = _member_count(db, forum.id)
    is_mem = _is_member(db, forum.id, caller.id) if caller else False
    return fs.ForumOut(
        id=forum.id,
        class_id=forum.class_id,
        name=forum.name,
        description=forum.description,
        status=forum.status,
        created_by=forum.created_by,
        approved_by=forum.approved_by,
        created_at=forum.created_at,
        updated_at=forum.updated_at,
        member_count=count,
        is_member=is_mem,
    )


def list_forums(
    db: DbSession, caller: im.User, class_id: uuid.UUID, include_pending: bool = False
) -> list[fs.ForumOut]:
    cls = db.get(im.Class, class_id)
    if cls is None:
        raise isvc.NotFoundError("Class not found.")
    _require_class_member(caller, class_id)
    is_rep = _is_class_rep_for(caller, class_id)
    q = select(fm.Forum).where(fm.Forum.class_id == class_id).order_by(fm.Forum.created_at)
    if not (include_pending and is_rep):
        q = q.where(fm.Forum.status == fm.ForumStatus.APPROVED)
    forums = db.scalars(q).all()
    return [_to_out(db, f, caller) for f in forums]


def list_pending(db: DbSession, caller: im.User, class_id: uuid.UUID) -> list[fs.ForumOut]:
    cls = db.get(im.Class, class_id)
    if cls is None:
        raise isvc.NotFoundError("Class not found.")
    _require_class_member(caller, class_id)
    if not _is_class_rep_for(caller, class_id):
        raise isvc.ForbiddenError("Only the class representative can view proposals.")
    q = (
        select(fm.Forum)
        .where(fm.Forum.class_id == class_id, fm.Forum.status == fm.ForumStatus.PENDING)
        .order_by(fm.Forum.created_at)
    )
    forums = db.scalars(q).all()
    return [_to_out(db, f, caller) for f in forums]


def propose_forum(
    db: DbSession, caller: im.User, class_id: uuid.UUID, data: fs.ForumCreateIn
) -> fs.ForumOut:
    cls = db.get(im.Class, class_id)
    if cls is None:
        raise isvc.NotFoundError("Class not found.")
    _require_class_member(caller, class_id)
    # Faculty/staff not allowed - they don't have verified class membership, so already blocked.
    # But explicitly ensure ROLE not FACULTY/STAFF even if they have class (edge defense).
    ident = _verified_identity_for_class(caller, class_id)
    assert ident is not None
    if ident.role in {im.Role.FACULTY, im.Role.STAFF, im.Role.UNIVERSITY_ADMIN, im.Role.DEPARTMENT_ADMIN}:
        raise isvc.ForbiddenError("Only students and class representatives can propose forums.")

    name = data.name.strip()
    if not name:
        raise isvc.ConflictError("Forum name must not be blank.")
    description = data.description.strip() if data.description else None
    # Unique per class (case-insensitive via lower): prevent duplicate names
    existing = db.scalar(select(fm.Forum).where(fm.Forum.class_id == class_id, func.lower(fm.Forum.name) == name.lower()))
    if existing is not None:
        raise isvc.ConflictError("A forum with this name already exists in this class.")

    forum = fm.Forum(
        class_id=class_id,
        name=name,
        description=description,
        status=fm.ForumStatus.PENDING,
        created_by=caller.id,
    )
    db.add(forum)
    db.commit()
    db.refresh(forum)
    return _to_out(db, forum, caller)


def get_forum(db: DbSession, caller: im.User, forum_id: uuid.UUID) -> fs.ForumOut:
    forum = db.get(fm.Forum, forum_id)
    if forum is None:
        raise isvc.NotFoundError("Forum not found.")
    # Enforce class isolation: caller must be verified member of forum's class
    _require_class_member(caller, forum.class_id)
    is_rep = _is_class_rep_for(caller, forum.class_id)
    is_creator = forum.created_by == caller.id
    if forum.status != fm.ForumStatus.APPROVED and not (is_rep or is_creator):
        # Hide non-approved forums from other class members (act as 404)
        raise isvc.NotFoundError("Forum not found.")
    return _to_out(db, forum, caller)


def review_forum(
    db: DbSession, caller: im.User, forum_id: uuid.UUID, new_status: fm.ForumStatus
) -> fs.ForumOut:
    if new_status not in (fm.ForumStatus.APPROVED, fm.ForumStatus.REJECTED):
        raise isvc.ConflictError("Status must be APPROVED or REJECTED.")
    forum = db.get(fm.Forum, forum_id)
    if forum is None:
        raise isvc.NotFoundError("Forum not found.")
    _require_class_member(caller, forum.class_id)
    if not _is_class_rep_for(caller, forum.class_id):
        raise isvc.ForbiddenError("Only the class representative can review proposals.")
    if forum.status != fm.ForumStatus.PENDING:
        raise isvc.ConflictError("Only pending proposals can be reviewed.")
    forum.status = new_status
    forum.approved_by = caller.id
    db.add(forum)
    db.commit()
    db.refresh(forum)
    return _to_out(db, forum, caller)


def join_forum(db: DbSession, caller: im.User, forum_id: uuid.UUID) -> fs.ForumOut:
    forum = db.get(fm.Forum, forum_id)
    if forum is None:
        raise isvc.NotFoundError("Forum not found.")
    if forum.status != fm.ForumStatus.APPROVED:
        raise isvc.NotFoundError("Forum not found.")
    _require_class_member(caller, forum.class_id)
    # Faculty/staff already blocked by class membership, but double-check
    ident = _verified_identity_for_class(caller, forum.class_id)
    assert ident is not None
    if ident.role in {im.Role.FACULTY, im.Role.STAFF, im.Role.UNIVERSITY_ADMIN, im.Role.DEPARTMENT_ADMIN}:
        raise isvc.ForbiddenError("Faculty and staff cannot join student class forums.")
    existing = db.scalar(
        select(fm.ForumMembership).where(
            fm.ForumMembership.forum_id == forum_id, fm.ForumMembership.user_id == caller.id
        )
    )
    if existing is not None:
        raise isvc.ConflictError("You are already a member of this forum.")
    ms = fm.ForumMembership(forum_id=forum_id, user_id=caller.id)
    db.add(ms)
    db.commit()
    return _to_out(db, forum, caller)


def leave_forum(db: DbSession, caller: im.User, forum_id: uuid.UUID) -> None:
    forum = db.get(fm.Forum, forum_id)
    if forum is None:
        raise isvc.NotFoundError("Forum not found.")
    # Class isolation still enforced
    _require_class_member(caller, forum.class_id)
    ms = db.scalar(
        select(fm.ForumMembership).where(
            fm.ForumMembership.forum_id == forum_id, fm.ForumMembership.user_id == caller.id
        )
    )
    if ms is None:
        raise isvc.NotFoundError("Membership not found.")
    db.delete(ms)
    db.commit()


def list_joined(db: DbSession, caller: im.User) -> list[fs.ForumOut]:
    # Joined forums are those where membership exists; filter to approved only? Include all but spec says approved forums become available
    q = (
        select(fm.Forum)
        .join(fm.ForumMembership, fm.ForumMembership.forum_id == fm.Forum.id)
        .where(fm.ForumMembership.user_id == caller.id)
        .order_by(fm.Forum.created_at)
    )
    forums = db.scalars(q).all()
    # Enforce class membership still? If user was moved, they might have orphan membership; but return anyway
    return [_to_out(db, f, caller) for f in forums]


# ── Discussion helpers ──

def _get_forum(db: DbSession, forum_id: uuid.UUID) -> fm.Forum:
    forum = db.get(fm.Forum, forum_id)
    if forum is None:
        raise isvc.NotFoundError("Forum not found.")
    if forum.status != fm.ForumStatus.APPROVED:
        raise isvc.NotFoundError("Forum not found.")
    return forum


def _require_forum_access(db: DbSession, caller: im.User, forum: fm.Forum) -> None:
    _require_class_member(caller, forum.class_id)


def _require_forum_member(db: DbSession, caller: im.User, forum: fm.Forum) -> None:
    _require_forum_access(db, caller, forum)
    if _is_class_rep_for(caller, forum.class_id):
        return
    if not _is_member(db, forum.id, caller.id):
        raise isvc.ForbiddenError("You must join this forum to perform this action.")


def _author_names(db: DbSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(im.User.id, im.Profile.display_name).join(im.Profile, im.Profile.user_id == im.User.id, isouter=True).where(im.User.id.in_(user_ids))
    ).all()
    return {uid: name for uid, name in rows}


def _enrich_posts(db: DbSession, posts: list[fm.Post], caller: im.User) -> list[fs.PostOut]:
    if not posts:
        return []
    ids = [p.id for p in posts]
    # like counts
    like_rows = db.execute(select(fm.PostReaction.post_id, func.count()).where(fm.PostReaction.post_id.in_(ids)).group_by(fm.PostReaction.post_id)).all()
    like_map = {pid: cnt for pid, cnt in like_rows}
    comment_rows = db.execute(select(fm.Comment.post_id, func.count()).where(fm.Comment.post_id.in_(ids)).group_by(fm.Comment.post_id)).all()
    comment_map = {pid: cnt for pid, cnt in comment_rows}
    liked_rows = db.scalars(select(fm.PostReaction.post_id).where(fm.PostReaction.user_id == caller.id, fm.PostReaction.post_id.in_(ids))).all()
    liked_set = set(liked_rows)
    author_ids = [p.author_id for p in posts if p.author_id]
    names = _author_names(db, author_ids)  # type: ignore[arg-type]
    out: list[fs.PostOut] = []
    for p in posts:
        out.append(
            fs.PostOut(
                id=p.id,
                forum_id=p.forum_id,
                author_id=p.author_id,
                author_display_name=names.get(p.author_id) if p.author_id else None,  # type: ignore[arg-type]
                content=p.content,
                created_at=p.created_at,
                updated_at=p.updated_at,
                like_count=like_map.get(p.id, 0),
                comment_count=comment_map.get(p.id, 0),
                liked_by_me=p.id in liked_set,
                is_own=p.author_id == caller.id,
            )
        )
    return out


def create_post(db: DbSession, caller: im.User, forum_id: uuid.UUID, data: fs.PostCreateIn) -> fs.PostOut:
    forum = _get_forum(db, forum_id)
    _require_forum_member(db, caller, forum)
    content = data.content.strip()
    if not content:
        raise isvc.ConflictError("Post content must not be blank.")
    post = fm.Post(forum_id=forum.id, author_id=caller.id, content=content)
    db.add(post)
    db.commit()
    db.refresh(post)
    # return with counts 0
    names = _author_names(db, [caller.id])
    return fs.PostOut(
        id=post.id,
        forum_id=post.forum_id,
        author_id=post.author_id,
        author_display_name=names.get(caller.id),
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        like_count=0,
        comment_count=0,
        liked_by_me=False,
        is_own=True,
    )


def list_posts(db: DbSession, caller: im.User, forum_id: uuid.UUID, limit: int, offset: int) -> fs.PostListOut:
    forum = _get_forum(db, forum_id)
    _require_forum_member(db, caller, forum)
    total = db.scalar(select(func.count()).select_from(fm.Post).where(fm.Post.forum_id == forum_id)) or 0
    q = select(fm.Post).where(fm.Post.forum_id == forum_id).order_by(fm.Post.created_at.desc(), fm.Post.id.desc()).limit(limit).offset(offset)
    posts = list(db.scalars(q).all())
    items = _enrich_posts(db, posts, caller)
    return fs.PostListOut(items=items, total=total, limit=limit, offset=offset)


def get_post(db: DbSession, caller: im.User, forum_id: uuid.UUID, post_id: uuid.UUID) -> fs.PostOut:
    forum = _get_forum(db, forum_id)
    _require_forum_member(db, caller, forum)
    post = db.get(fm.Post, post_id)
    if post is None or post.forum_id != forum.id:
        raise isvc.NotFoundError("Post not found.")
    return _enrich_posts(db, [post], caller)[0]


def delete_post(db: DbSession, caller: im.User, forum_id: uuid.UUID, post_id: uuid.UUID) -> None:
    forum = _get_forum(db, forum_id)
    # Need class membership baseline to ensure cross-class blocked properly
    _require_forum_access(db, caller, forum)
    post = db.get(fm.Post, post_id)
    if post is None or post.forum_id != forum.id:
        raise isvc.NotFoundError("Post not found.")
    is_own = post.author_id == caller.id
    is_rep = _is_class_rep_for(caller, forum.class_id)
    if not (is_own or is_rep):
        raise isvc.ForbiddenError("You do not have permission to delete this post.")
    # If rep but not member and not own, still allowed if rep of class
    # If non-member non-rep, delete blocked already via Forbidden above? Actually need membership check for own deletion.
    if is_own and not is_rep:
        # own post requires membership
        _require_forum_member(db, caller, forum)
    db.delete(post)
    db.commit()


def create_comment(db: DbSession, caller: im.User, forum_id: uuid.UUID, post_id: uuid.UUID, data: fs.CommentCreateIn) -> fs.CommentOut:
    forum = _get_forum(db, forum_id)
    _require_forum_member(db, caller, forum)
    post = db.get(fm.Post, post_id)
    if post is None or post.forum_id != forum.id:
        raise isvc.NotFoundError("Post not found.")
    content = data.content.strip()
    if not content:
        raise isvc.ConflictError("Comment content must not be blank.")
    comment = fm.Comment(post_id=post.id, author_id=caller.id, content=content)
    db.add(comment)
    db.flush()
    # Notification: someone comments on your post
    if post.author_id and post.author_id != caller.id:
        notif = fm.Notification(
            user_id=post.author_id,
            actor_id=caller.id,
            type="COMMENT_ON_POST",
            post_id=post.id,
            forum_id=forum.id,
            comment_id=comment.id,
            message=f"Someone commented on your post in {forum.name}",
        )
        db.add(notif)
    db.commit()
    db.refresh(comment)
    names = _author_names(db, [caller.id])
    return fs.CommentOut(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        author_display_name=names.get(caller.id),
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        is_own=True,
    )


def list_comments(db: DbSession, caller: im.User, forum_id: uuid.UUID, post_id: uuid.UUID, limit: int, offset: int) -> fs.CommentListOut:
    forum = _get_forum(db, forum_id)
    _require_forum_member(db, caller, forum)
    post = db.get(fm.Post, post_id)
    if post is None or post.forum_id != forum.id:
        raise isvc.NotFoundError("Post not found.")
    total = db.scalar(select(func.count()).select_from(fm.Comment).where(fm.Comment.post_id == post_id)) or 0
    q = select(fm.Comment).where(fm.Comment.post_id == post_id).order_by(fm.Comment.created_at.asc()).limit(limit).offset(offset)
    comments = list(db.scalars(q).all())
    author_ids = [c.author_id for c in comments if c.author_id]
    names = _author_names(db, author_ids)  # type: ignore[arg-type]
    items = [
        fs.CommentOut(
            id=c.id,
            post_id=c.post_id,
            author_id=c.author_id,
            author_display_name=names.get(c.author_id) if c.author_id else None,  # type: ignore[arg-type]
            content=c.content,
            created_at=c.created_at,
            updated_at=c.updated_at,
            is_own=c.author_id == caller.id,
        )
        for c in comments
    ]
    return fs.CommentListOut(items=items, total=total, limit=limit, offset=offset)


def delete_comment(db: DbSession, caller: im.User, forum_id: uuid.UUID, post_id: uuid.UUID, comment_id: uuid.UUID) -> None:
    forum = _get_forum(db, forum_id)
    _require_forum_access(db, caller, forum)
    post = db.get(fm.Post, post_id)
    if post is None or post.forum_id != forum.id:
        raise isvc.NotFoundError("Post not found.")
    comment = db.get(fm.Comment, comment_id)
    if comment is None or comment.post_id != post.id:
        raise isvc.NotFoundError("Comment not found.")
    is_own = comment.author_id == caller.id
    is_rep = _is_class_rep_for(caller, forum.class_id)
    if not (is_own or is_rep):
        raise isvc.ForbiddenError("You do not have permission to delete this comment.")
    if is_own and not is_rep:
        _require_forum_member(db, caller, forum)
    db.delete(comment)
    db.commit()


def like_post(db: DbSession, caller: im.User, forum_id: uuid.UUID, post_id: uuid.UUID) -> dict:
    forum = _get_forum(db, forum_id)
    _require_forum_member(db, caller, forum)
    post = db.get(fm.Post, post_id)
    if post is None or post.forum_id != forum.id:
        raise isvc.NotFoundError("Post not found.")
    existing = db.scalar(select(fm.PostReaction).where(fm.PostReaction.post_id == post.id, fm.PostReaction.user_id == caller.id))
    if existing is not None:
        raise isvc.ConflictError("You have already liked this post.")
    db.add(fm.PostReaction(post_id=post.id, user_id=caller.id))
    db.commit()
    cnt = db.scalar(select(func.count()).select_from(fm.PostReaction).where(fm.PostReaction.post_id == post.id)) or 0
    return {"like_count": cnt, "liked": True}


def unlike_post(db: DbSession, caller: im.User, forum_id: uuid.UUID, post_id: uuid.UUID) -> dict:
    forum = _get_forum(db, forum_id)
    _require_forum_member(db, caller, forum)
    post = db.get(fm.Post, post_id)
    if post is None or post.forum_id != forum.id:
        raise isvc.NotFoundError("Post not found.")
    existing = db.scalar(select(fm.PostReaction).where(fm.PostReaction.post_id == post.id, fm.PostReaction.user_id == caller.id))
    if existing is None:
        raise isvc.NotFoundError("Like not found.")
    db.delete(existing)
    db.commit()
    cnt = db.scalar(select(func.count()).select_from(fm.PostReaction).where(fm.PostReaction.post_id == post.id)) or 0
    return {"like_count": cnt, "liked": False}


def list_notifications(db: DbSession, caller: im.User, limit: int, offset: int) -> list[fs.NotificationOut]:
    q = select(fm.Notification).where(fm.Notification.user_id == caller.id).order_by(fm.Notification.created_at.desc()).limit(limit).offset(offset)
    rows = db.scalars(q).all()
    return [fs.NotificationOut.model_validate(r) for r in rows]


def mark_notification_read(db: DbSession, caller: im.User, notif_id: uuid.UUID) -> fs.NotificationOut:
    notif = db.get(fm.Notification, notif_id)
    if notif is None or notif.user_id != caller.id:
        raise isvc.NotFoundError("Notification not found.")
    notif.is_read = True
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return fs.NotificationOut.model_validate(notif)
