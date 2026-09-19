"""Identity service: registration, verification, sessions, admin actions.

Verification rule (demo-honest, no fake ERP integration):
a registering student supplies university + class + student_no +
enrollment_code from their university email context. The identity becomes
VERIFIED immediately only if ALL hold:
  1. the class belongs to the university (chain class→batch→program→
     department→university validated),
  2. the email domain matches the university's email_domain,
  3. the enrollment code matches the university's code (Argon2 hash compare),
  4. the student_no is not already taken at that university.
Otherwise the identity is PENDING for admin review. Students can never
self-verify: the VERIFIED transition happens here (server-side, against
university-controlled data) or via the admin endpoint.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession, joinedload

from fastapi import status

from app.core.errors import AppError
from app.modules.identity import models as m
from app.modules.identity import schemas as s
from app.modules.identity import security as sec


class ConflictError(AppError):
    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, message: str):
        self.message = message


class AuthError(AppError):
    code = "AUTH_FAILED"
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, message: str = "Invalid email or password."):
        self.message = message


class ForbiddenError(AppError):
    code = "FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, message: str = "You do not have permission to perform this action."):
        self.message = message


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, message: str = "Resource not found."):
        self.message = message


ADMIN_ROLES = {m.Role.UNIVERSITY_ADMIN, m.Role.DEPARTMENT_ADMIN}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime) -> bool:
    # SQLite returns naive datetimes; Postgres returns aware ones. Normalize.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= _utcnow()


def _identity_to_out(ident: m.UniversityIdentity) -> s.IdentityOut:
    return s.IdentityOut(
        id=ident.id,
        university_id=ident.university_id,
        university_name=ident.university.name if ident.university else None,
        role=ident.role,
        status=ident.status,
        student_no=ident.student_no,
        class_id=ident.class_id,
        class_name=ident.class_.name if ident.class_ else None,
        verified_at=ident.verified_at,
    )


def me_out(user: m.User) -> s.MeOut:
    profile = user.profile
    return s.MeOut(
        id=user.id,
        email=user.email,
        profile=s.ProfileOut(
            display_name=profile.display_name if profile else None,
            bio=profile.bio if profile else None,
        ),
        identities=[_identity_to_out(i) for i in user.identities],
    )


def _load_class_chain(db: DbSession, class_id: object) -> tuple[m.Class, m.University]:
    cls = db.get(m.Class, class_id)  # type: ignore[arg-type]
    if cls is None:
        raise NotFoundError("Class not found.")
    university = cls.batch.program.department.university
    return cls, university


def register(db: DbSession, data: s.RegisterIn, session_expire_days: int) -> tuple[m.User, str]:
    email = data.email.strip().lower()

    existing = db.scalar(select(m.User).where(m.User.email == email))
    if existing is not None:
        raise ConflictError("An account with this email already exists.")

    cls, university = _load_class_chain(db, data.class_id)
    if university.id != data.university_id:
        raise ConflictError("The selected class does not belong to the selected university.")

    taken = db.scalar(
        select(m.UniversityIdentity).where(
            m.UniversityIdentity.university_id == university.id,
            m.UniversityIdentity.student_no == data.student_no,
        )
    )
    if taken is not None:
        raise ConflictError("This student number is already registered at this university.")

    domain_ok = email.endswith("@" + university.email_domain.lower())
    try:
        code_ok = sec.verify_password(university.enrollment_code_hash, data.enrollment_code.strip())
    except Exception:
        code_ok = False

    user = m.User(email=email, password_hash=sec.hash_password(data.password))
    db.add(user)
    db.flush()  # assign user.id

    db.add(m.Profile(user_id=user.id, display_name=data.display_name))

    verified = domain_ok and code_ok
    now = _utcnow()
    db.add(
        m.UniversityIdentity(
            user_id=user.id,
            university_id=university.id,
            role=m.Role.STUDENT,
            status=m.IdentityStatus.VERIFIED if verified else m.IdentityStatus.PENDING,
            student_no=data.student_no,
            class_id=cls.id,
            verified_at=now if verified else None,
        )
    )

    token, expires_at = _new_session(db, user, session_expire_days)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("An account with this email already exists.")
    return user, token


def _new_session(db: DbSession, user: m.User, expire_days: int) -> tuple[str, datetime]:
    token = sec.new_token()
    expires_at = _utcnow() + timedelta(days=expire_days)
    db.add(m.Session(user_id=user.id, token_hash=sec.hash_token(token), expires_at=expires_at))
    db.flush()
    return token, expires_at


def authenticate(db: DbSession, email: str, password: str, session_expire_days: int) -> tuple[m.User, str]:
    email = email.strip().lower()
    user = db.scalar(select(m.User).where(m.User.email == email))
    if user is None or not user.is_active or not sec.verify_password(user.password_hash, password):
        raise AuthError()
    if sec.needs_rehash(user.password_hash):
        user.password_hash = sec.hash_password(password)
        db.add(user)
    token, _ = _new_session(db, user, session_expire_days)
    db.commit()
    return user, token


def logout(db: DbSession, token: str) -> None:
    sess = db.scalar(select(m.Session).where(m.Session.token_hash == sec.hash_token(token)))
    if sess is not None and sess.revoked_at is None:
        sess.revoked_at = _utcnow()
        db.add(sess)
        db.commit()


def get_session_user(db: DbSession, token: str) -> m.User | None:
    sess = (
        db.execute(
            select(m.Session)
            .options(joinedload(m.Session.user).joinedload(m.User.profile))
            .where(m.Session.token_hash == sec.hash_token(token))
        )
        .scalars()
        .first()
    )
    if sess is None or sess.revoked_at is not None or _is_expired(sess.expires_at):
        return None
    if not sess.user.is_active:
        return None
    # Load identities with university/class eager to avoid lazy-load issues.
    db.execute(
        select(m.UniversityIdentity)
        .options(joinedload(m.UniversityIdentity.university), joinedload(m.UniversityIdentity.class_))
        .where(m.UniversityIdentity.user_id == sess.user.id)
    ).scalars().all()
    return sess.user


def update_profile(db: DbSession, user: m.User, data: s.ProfileUpdateIn) -> m.Profile:
    profile = user.profile
    if profile is None:
        profile = m.Profile(user_id=user.id)
        db.add(profile)
    if data.display_name is not None:
        profile.display_name = data.display_name
    if data.bio is not None:
        profile.bio = data.bio
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def is_admin_of(user: m.User, university_id: object) -> bool:
    for ident in user.identities:
        if (
            ident.university_id == university_id
            and ident.status == m.IdentityStatus.VERIFIED
            and ident.role in ADMIN_ROLES
        ):
            return True
    return False


def admin_update_identity(
    db: DbSession, admin: m.User, identity_id: object, data: s.AdminIdentityUpdateIn
) -> m.UniversityIdentity:
    ident = db.get(m.UniversityIdentity, identity_id)  # type: ignore[arg-type]
    if ident is None:
        raise NotFoundError("Identity not found.")
    if not is_admin_of(admin, ident.university_id):
        raise ForbiddenError("Admin rights at this university are required.")
    if data.status is not None:
        ident.status = data.status
        ident.verified_at = _utcnow() if data.status == m.IdentityStatus.VERIFIED else ident.verified_at
    if data.role is not None:
        ident.role = data.role
    db.add(ident)
    db.commit()
    db.refresh(ident, attribute_names=["university", "class_"])
    return ident
