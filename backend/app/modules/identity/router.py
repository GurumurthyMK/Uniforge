"""Identity API: public directory, auth, profile, admin moderation."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from fastapi import APIRouter, Depends, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DbSession

from app.core.config import get_settings
from app.db.session import get_db
from app.modules.identity import models as m
from app.modules.identity import schemas as s
from app.modules.identity import security as sec
from app.modules.identity import service as svc
from app.modules.identity.deps import get_current_user

router = APIRouter(tags=["identity"])
_bearer = HTTPBearer(auto_error=False)


def _full_user(db: DbSession, user_id: uuid.UUID) -> m.User:
    full = (
        db.execute(
            select(m.User)
            .options(
                joinedload(m.User.profile),
                joinedload(m.User.identities).joinedload(m.UniversityIdentity.university),
                joinedload(m.User.identities).joinedload(m.UniversityIdentity.class_),
            )
            .where(m.User.id == user_id)
        )
        .scalars()
        .first()
    )
    assert full is not None
    return full


# ---- Public directory (needed pre-auth for the registration form) ----


@router.get("/universities", response_model=list[s.UniversityOut])
def list_universities(db: DbSession = Depends(get_db)) -> list[m.University]:
    return list(db.scalars(select(m.University).order_by(m.University.name)).all())


@router.get("/universities/{university_id}/classes", response_model=list[s.ClassOut])
def list_classes(
    university_id: uuid.UUID,
    db: DbSession = Depends(get_db),
) -> list[s.ClassOut]:
    rows = (
        db.execute(
            select(m.Class, m.Batch, m.Program, m.Department)
            .join(m.Batch, m.Class.batch_id == m.Batch.id)
            .join(m.Program, m.Batch.program_id == m.Program.id)
            .join(m.Department, m.Program.department_id == m.Department.id)
            .where(m.Department.university_id == university_id)
            .order_by(m.Class.name)
        )
        .all()
    )
    return [
        s.ClassOut(
            id=cls.id,
            batch_id=cls.batch_id,
            name=cls.name,
            code=cls.code,
            batch_name=batch.name,
            program_name=program.name,
            department_name=department.name,
        )
        for cls, batch, program, department in rows
    ]


# ---- Auth ----


@router.post("/auth/register", response_model=s.AuthOut, status_code=201)
def register(data: s.RegisterIn, db: DbSession = Depends(get_db)) -> s.AuthOut:
    settings = get_settings()
    user, token = svc.register(db, data, settings.session_expire_days)
    sess = db.scalar(select(m.Session).where(m.Session.token_hash == sec.hash_token(token)))
    assert sess is not None
    return s.AuthOut(token=token, expires_at=sess.expires_at, user=svc.me_out(_full_user(db, user.id)))


@router.post("/auth/login", response_model=s.AuthOut)
def login(data: s.LoginIn, db: DbSession = Depends(get_db)) -> s.AuthOut:
    settings = get_settings()
    user, token = svc.authenticate(db, str(data.email), data.password, settings.session_expire_days)
    sess = db.scalar(select(m.Session).where(m.Session.token_hash == sec.hash_token(token)))
    assert sess is not None
    return s.AuthOut(token=token, expires_at=sess.expires_at, user=svc.me_out(_full_user(db, user.id)))


@router.post("/auth/logout", status_code=204)
def logout(
    db: DbSession = Depends(get_db),
    user: m.User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Response:
    assert credentials is not None and credentials.credentials
    svc.logout(db, credentials.credentials)
    return Response(status_code=204)


@router.get("/auth/me", response_model=s.MeOut)
def me(user: m.User = Depends(get_current_user)) -> s.MeOut:
    return svc.me_out(user)


# ---- Student-controlled profile ----


@router.patch("/auth/profile", response_model=s.ProfileOut)
def update_profile(
    data: s.ProfileUpdateIn,
    db: DbSession = Depends(get_db),
    user: m.User = Depends(get_current_user),
) -> s.ProfileOut:
    profile = svc.update_profile(db, user, data)
    return s.ProfileOut(display_name=profile.display_name, bio=profile.bio)


# ---- Admin moderation (server-side authorized; never a frontend concern) ----


@router.get("/admin/identities", response_model=list[s.IdentityOut])
def admin_list_identities(
    university_id: uuid.UUID = Query(...),
    status_filter: m.IdentityStatus | None = Query(default=None, alias="status"),
    db: DbSession = Depends(get_db),
    admin: m.User = Depends(get_current_user),
) -> list[s.IdentityOut]:
    if not svc.is_admin_of(admin, university_id):
        raise svc.ForbiddenError("Admin rights at this university are required.")
    q = (
        select(m.UniversityIdentity)
        .options(joinedload(m.UniversityIdentity.university), joinedload(m.UniversityIdentity.class_))
        .where(m.UniversityIdentity.university_id == university_id)
        .order_by(m.UniversityIdentity.created_at)
    )
    if status_filter is not None:
        q = q.where(m.UniversityIdentity.status == status_filter)
    return [svc._identity_to_out(i) for i in db.scalars(q).all()]


@router.patch("/admin/identities/{identity_id}", response_model=s.IdentityOut)
def admin_update_identity(
    identity_id: uuid.UUID,
    data: s.AdminIdentityUpdateIn,
    db: DbSession = Depends(get_db),
    admin: m.User = Depends(get_current_user),
) -> s.IdentityOut:
    ident = svc.admin_update_identity(db, admin, identity_id, data)
    return svc._identity_to_out(ident)
