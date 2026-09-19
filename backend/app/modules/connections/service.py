"""Connection service: authorization, state machine, queries."""

import uuid

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.modules.connections import models as cm
from app.modules.connections import schemas as cs
from app.modules.forum import models as fm
from app.modules.identity import models as im
from app.modules.identity import service as isvc

ALLOWED_STUDENT_ROLES = {im.Role.STUDENT, im.Role.CLASS_REP}


def _verified_student_identity(user: im.User) -> im.UniversityIdentity | None:
    for ident in user.identities:
        if ident.status == im.IdentityStatus.VERIFIED and ident.role in ALLOWED_STUDENT_ROLES:
            return ident
    return None


def _same_university(user_a: im.User, user_b: im.User) -> bool:
    a_idents = {i.university_id for i in user_a.identities if i.status == im.IdentityStatus.VERIFIED and i.role in ALLOWED_STUDENT_ROLES}
    b_idents = {i.university_id for i in user_b.identities if i.status == im.IdentityStatus.VERIFIED and i.role in ALLOWED_STUDENT_ROLES}
    return bool(a_idents & b_idents)


def _require_verified_student(user: im.User) -> im.UniversityIdentity:
    ident = _verified_student_identity(user)
    if ident is None:
        raise isvc.ForbiddenError("Only verified students can manage connections.")
    return ident


def _get_user(db: DbSession, user_id: uuid.UUID) -> im.User:
    user = db.get(im.User, user_id)
    if user is None or not user.is_active:
        raise isvc.NotFoundError("User not found.")
    # ensure identities loaded
    db.refresh(user, attribute_names=["identities"])
    return user


def _find_connection(db: DbSession, a: uuid.UUID, b: uuid.UUID) -> cm.Connection | None:
    """Find any connection between a and b in either direction."""
    return db.scalar(
        select(cm.Connection).where(
            or_(
                and_(cm.Connection.requester_id == a, cm.Connection.recipient_id == b),
                and_(cm.Connection.requester_id == b, cm.Connection.recipient_id == a),
            )
        )
    )


def _find_directional(db: DbSession, requester: uuid.UUID, recipient: uuid.UUID) -> cm.Connection | None:
    return db.scalar(
        select(cm.Connection).where(
            cm.Connection.requester_id == requester, cm.Connection.recipient_id == recipient
        )
    )


def _profile_info(db: DbSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(im.User.id, im.Profile.display_name, im.Profile.headline, im.Profile.avatar_url)
        .join(im.Profile, im.Profile.user_id == im.User.id, isouter=True)
        .where(im.User.id.in_(user_ids))
    ).all()
    base = {uid: {"display_name": dn, "headline": hl, "avatar_url": av} for uid, dn, hl, av in rows}
    # batch fetch verified student identities to avoid N+1
    idents = db.execute(
        select(im.UniversityIdentity.user_id, im.UniversityIdentity.role, im.UniversityIdentity.status).where(
            im.UniversityIdentity.user_id.in_(user_ids),
            im.UniversityIdentity.status == im.IdentityStatus.VERIFIED,
            im.UniversityIdentity.role.in_(list(ALLOWED_STUDENT_ROLES)),
        )
    ).all()
    # keep first per user (deterministic)
    seen: set[uuid.UUID] = set()
    for uid, role, status in idents:
        if uid in seen:
            continue
        seen.add(uid)
        if uid in base:
            base[uid]["role"] = role.value if hasattr(role, "value") else str(role)
            base[uid]["verification_status"] = status.value if hasattr(status, "value") else str(status)
    return base


def _to_user_out(db: DbSession, user_id: uuid.UUID, conn: cm.Connection | None) -> cs.ConnectionUserOut:
    info = _profile_info(db, [user_id])
    p = info.get(user_id, {})
    return cs.ConnectionUserOut(
        user_id=user_id,
        display_name=p.get("display_name"),
        headline=p.get("headline"),
        avatar_url=p.get("avatar_url"),
        role=p.get("role"),
        verification_status=p.get("verification_status"),
        connection_id=conn.id if conn else None,
        status=conn.status if conn else None,
        created_at=conn.created_at if conn else None,
        updated_at=conn.updated_at if conn else None,
    )


def send_request(db: DbSession, requester: im.User, recipient_id: uuid.UUID) -> cm.Connection:
    _require_verified_student(requester)
    if requester.id == recipient_id:
        raise isvc.ConflictError("You cannot connect to yourself.")
    recipient = _get_user(db, recipient_id)
    rec_ident = _verified_student_identity(recipient)
    if rec_ident is None:
        raise isvc.ForbiddenError("Target user is not a verified student.")
    if not _same_university(requester, recipient):
        raise isvc.ForbiddenError("Cross-university connections are not allowed.")

    existing = _find_connection(db, requester.id, recipient_id)
    if existing is not None:
        if existing.status == cm.ConnectionStatus.REJECTED:
            # Allow new request: delete old rejected row
            db.delete(existing)
            db.flush()
        elif existing.status == cm.ConnectionStatus.PENDING:
            raise isvc.ConflictError("A pending connection already exists.")
        elif existing.status == cm.ConnectionStatus.ACCEPTED:
            raise isvc.ConflictError("You are already connected.")
        else:
            raise isvc.ConflictError("A connection already exists.")

    conn = cm.Connection(requester_id=requester.id, recipient_id=recipient_id, status=cm.ConnectionStatus.PENDING)
    db.add(conn)
    db.flush()
    # notification for recipient
    db.add(
        fm.Notification(
            user_id=recipient_id,
            actor_id=requester.id,
            type="CONNECTION_REQUEST",
            message="A student sent you a connection request.",
        )
    )
    db.commit()
    db.refresh(conn)
    return conn


def accept_request(db: DbSession, recipient: im.User, requester_id: uuid.UUID) -> cm.Connection:
    _require_verified_student(recipient)
    conn = _find_directional(db, requester_id, recipient.id)
    if conn is None or conn.status != cm.ConnectionStatus.PENDING:
        raise isvc.NotFoundError("Connection request not found.")
    # ensure requester is verified student same university (defense)
    requester = _get_user(db, requester_id)
    if not _same_university(recipient, requester):
        raise isvc.ForbiddenError("Cross-university connection invalid.")
    conn.status = cm.ConnectionStatus.ACCEPTED
    db.add(conn)
    db.flush()
    db.add(
        fm.Notification(
            user_id=requester_id,
            actor_id=recipient.id,
            type="CONNECTION_ACCEPTED",
            message="Your connection request was accepted.",
        )
    )
    db.commit()
    db.refresh(conn)
    return conn


def reject_request(db: DbSession, recipient: im.User, requester_id: uuid.UUID) -> cm.Connection:
    _require_verified_student(recipient)
    conn = _find_directional(db, requester_id, recipient.id)
    if conn is None or conn.status != cm.ConnectionStatus.PENDING:
        raise isvc.NotFoundError("Connection request not found.")
    conn.status = cm.ConnectionStatus.REJECTED
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def cancel_request(db: DbSession, requester: im.User, recipient_id: uuid.UUID) -> None:
    _require_verified_student(requester)
    conn = _find_directional(db, requester.id, recipient_id)
    if conn is None or conn.status != cm.ConnectionStatus.PENDING:
        raise isvc.NotFoundError("Pending request not found.")
    # only requester can cancel: we already checked direction
    db.delete(conn)
    db.commit()


def remove_connection(db: DbSession, caller: im.User, other_id: uuid.UUID) -> None:
    _require_verified_student(caller)
    conn = _find_connection(db, caller.id, other_id)
    if conn is None or conn.status != cm.ConnectionStatus.ACCEPTED:
        raise isvc.NotFoundError("Connection not found.")
    db.delete(conn)
    db.commit()


def list_connections(db: DbSession, user: im.User) -> list[cs.ConnectionUserOut]:
    _require_verified_student(user)
    rows = db.scalars(
        select(cm.Connection).where(
            cm.Connection.status == cm.ConnectionStatus.ACCEPTED,
            or_(cm.Connection.requester_id == user.id, cm.Connection.recipient_id == user.id),
        )
    ).all()
    other_ids: list[uuid.UUID] = []
    conn_map: dict[uuid.UUID, cm.Connection] = {}
    for c in rows:
        other = c.recipient_id if c.requester_id == user.id else c.requester_id
        other_ids.append(other)
        conn_map[other] = c
    if not other_ids:
        return []
    # batch profile info
    info = _profile_info(db, other_ids)
    out: list[cs.ConnectionUserOut] = []
    for oid in other_ids:
        p = info.get(oid, {})
        conn = conn_map[oid]
        out.append(
            cs.ConnectionUserOut(
                user_id=oid,
                display_name=p.get("display_name"),
                headline=p.get("headline"),
                avatar_url=p.get("avatar_url"),
                role=p.get("role"),
                verification_status=p.get("verification_status"),
                connection_id=conn.id,
                status=conn.status,
                created_at=conn.created_at,
                updated_at=conn.updated_at,
            )
        )
    return out


def list_incoming(db: DbSession, user: im.User) -> list[cs.ConnectionUserOut]:
    _require_verified_student(user)
    rows = db.scalars(
        select(cm.Connection).where(
            cm.Connection.recipient_id == user.id, cm.Connection.status == cm.ConnectionStatus.PENDING
        )
    ).all()
    if not rows:
        return []
    ids = [r.requester_id for r in rows]
    info = _profile_info(db, ids)
    out = []
    for r in rows:
        p = info.get(r.requester_id, {})
        out.append(
            cs.ConnectionUserOut(
                user_id=r.requester_id,
                display_name=p.get("display_name"),
                headline=p.get("headline"),
                avatar_url=p.get("avatar_url"),
                role=p.get("role"),
                verification_status=p.get("verification_status"),
                connection_id=r.id,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return out


def list_outgoing(db: DbSession, user: im.User) -> list[cs.ConnectionUserOut]:
    _require_verified_student(user)
    rows = db.scalars(
        select(cm.Connection).where(
            cm.Connection.requester_id == user.id, cm.Connection.status == cm.ConnectionStatus.PENDING
        )
    ).all()
    if not rows:
        return []
    ids = [r.recipient_id for r in rows]
    info = _profile_info(db, ids)
    out = []
    for r in rows:
        p = info.get(r.recipient_id, {})
        out.append(
            cs.ConnectionUserOut(
                user_id=r.recipient_id,
                display_name=p.get("display_name"),
                headline=p.get("headline"),
                avatar_url=p.get("avatar_url"),
                role=p.get("role"),
                verification_status=p.get("verification_status"),
                connection_id=r.id,
                status=r.status,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return out


def get_status(db: DbSession, caller: im.User, other_id: uuid.UUID) -> cs.ConnectionStatusOut:
    _require_verified_student(caller)
    if caller.id == other_id:
        return cs.ConnectionStatusOut(status="SELF", connection=None)
    _get_user(db, other_id)  # ensure exists, will raise 404 if not
    conn = _find_connection(db, caller.id, other_id)
    if conn is None:
        return cs.ConnectionStatusOut(status="NONE", connection=None)
    if conn.status == cm.ConnectionStatus.ACCEPTED:
        return cs.ConnectionStatusOut(status="CONNECTED", connection=conn)
    if conn.status == cm.ConnectionStatus.PENDING:
        if conn.requester_id == caller.id:
            return cs.ConnectionStatusOut(status="PENDING_OUTGOING", connection=conn)
        else:
            return cs.ConnectionStatusOut(status="PENDING_INCOMING", connection=conn)
    if conn.status == cm.ConnectionStatus.REJECTED:
        # For rejected, return REJECTED if caller was requester, else also REJECTED
        # Frontend can treat as NONE, but we expose explicitly
        return cs.ConnectionStatusOut(status="REJECTED", connection=conn)
    return cs.ConnectionStatusOut(status="NONE", connection=None)


def _connected_ids(db: DbSession, user_id: uuid.UUID) -> set[uuid.UUID]:
    rows = db.execute(
        select(cm.Connection.requester_id, cm.Connection.recipient_id).where(
            cm.Connection.status == cm.ConnectionStatus.ACCEPTED,
            or_(cm.Connection.requester_id == user_id, cm.Connection.recipient_id == user_id),
        )
    ).all()
    ids: set[uuid.UUID] = set()
    for req, rec in rows:
        other = rec if req == user_id else req
        ids.add(other)
    return ids


def mutual_connections(db: DbSession, caller: im.User, other_id: uuid.UUID) -> cs.MutualsOut:
    _require_verified_student(caller)
    other = _get_user(db, other_id)
    # verify same university
    if not _same_university(caller, other):
        raise isvc.ForbiddenError("Cross-university mutuals not allowed.")
    my_ids = _connected_ids(db, caller.id)
    other_ids = _connected_ids(db, other_id)
    mutual_ids = list(my_ids & other_ids)
    if not mutual_ids:
        return cs.MutualsOut(count=0, users=[])
    info = _profile_info(db, mutual_ids)
    users = []
    for mid in mutual_ids:
        p = info.get(mid, {})
        users.append(
            cs.ConnectionUserOut(
                user_id=mid,
                display_name=p.get("display_name"),
                headline=p.get("headline"),
                avatar_url=p.get("avatar_url"),
                role=p.get("role"),
                verification_status=p.get("verification_status"),
            )
        )
    # sort deterministically by display_name
    users.sort(key=lambda u: (u.display_name or "", str(u.user_id)))
    return cs.MutualsOut(count=len(users), users=users)
