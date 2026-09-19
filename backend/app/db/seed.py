"""Development seed: demo university + academic structure + demo users.

Idempotent: safe to re-run; existing rows are reused (passwords are reset to
the documented demo password so logins keep working after re-seed).

Demo credentials (password for ALL demo users: ``Demo1234!``)::

    admin@demo-university.edu       UNIVERSITY_ADMIN
    deptadmin@demo-university.edu   DEPARTMENT_ADMIN
    prof@demo-university.edu        FACULTY
    officer@demo-university.edu     STAFF
    rep@demo-university.edu         CLASS_REP (class CS-2024-A)
    ada@demo-university.edu         STUDENT (CS-2024-A)
    ben@demo-university.edu         STUDENT (CS-2024-A)
    cara@demo-university.edu        STUDENT (CS-2024-B)

Demo enrollment code for self-registration: ``UNIFORGE-DEMO-2026``

Run:  ``python -m app.db.seed`` from ``backend/`` (uses app settings).
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session_factory
from app.modules.identity import models as m
from app.modules.identity import security as sec

DEMO_PASSWORD = "Demo1234!"
DEMO_ENROLLMENT_CODE = "UNIFORGE-DEMO-2026"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create(db: Session, model: type[m.Base], defaults: dict, **filters):  # type: ignore[valid-type]
    row = db.scalar(select(model).filter_by(**filters))
    if row is not None:
        return row, False
    row = model(**{**filters, **defaults})
    db.add(row)
    db.flush()
    return row, True


def seed(db: Session) -> dict[str, int]:
    created = {"universities": 0, "users": 0}

    uni, made = get_or_create(
        db,
        m.University,
        dict(
            name="Demo University",
            email_domain="demo-university.edu",
            enrollment_code_hash=sec.hash_password(DEMO_ENROLLMENT_CODE),
            city="Berlin",
            country="Germany",
        ),
        code="DEMO-U",
    )
    created["universities"] += int(made)

    cs, _ = get_or_create(db, m.Department, dict(name="Computer Science"), university_id=uni.id, code="CS")
    ba, _ = get_or_create(db, m.Department, dict(name="Business Administration"), university_id=uni.id, code="BA")

    bsc, _ = get_or_create(
        db, m.Program, dict(name="BSc Computer Science", degree_level="BSc"), department_id=cs.id, code="CS-BSC"
    )
    msc, _ = get_or_create(
        db, m.Program, dict(name="MSc Data Science", degree_level="MSc"), department_id=cs.id, code="DS-MSC"
    )
    bba, _ = get_or_create(
        db, m.Program, dict(name="BBA", degree_level="BBA"), department_id=ba.id, code="BBA"
    )

    b24, _ = get_or_create(db, m.Batch, dict(start_year=2024), program_id=bsc.id, name="2024")
    b25, _ = get_or_create(db, m.Batch, dict(start_year=2025), program_id=bsc.id, name="2025")
    d24, _ = get_or_create(db, m.Batch, dict(start_year=2024), program_id=msc.id, name="2024")
    a24, _ = get_or_create(db, m.Batch, dict(start_year=2024), program_id=bba.id, name="2024")

    csa, _ = get_or_create(db, m.Class, dict(name="CS-2024-A"), batch_id=b24.id, code="A")
    csb, _ = get_or_create(db, m.Class, dict(name="CS-2024-B"), batch_id=b24.id, code="B")
    get_or_create(db, m.Class, dict(name="CS-2025-A"), batch_id=b25.id, code="A")
    get_or_create(db, m.Class, dict(name="DS-2024-A"), batch_id=d24.id, code="A")
    get_or_create(db, m.Class, dict(name="BBA-2024-A"), batch_id=a24.id, code="A")

    demo_users: list[tuple[str, str, m.Role, str | None, m.Class | None]] = [
        ("admin@demo-university.edu", "Uni Admin", m.Role.UNIVERSITY_ADMIN, None, None),
        ("deptadmin@demo-university.edu", "Dept Admin", m.Role.DEPARTMENT_ADMIN, None, None),
        ("prof@demo-university.edu", "Prof. Ada Lovelace", m.Role.FACULTY, None, None),
        ("officer@demo-university.edu", "Staff Officer", m.Role.STAFF, None, None),
        ("rep@demo-university.edu", "Class Rep", m.Role.CLASS_REP, "DEMO-2024-090", csa),
        ("ada@demo-university.edu", "Ada Student", m.Role.STUDENT, "DEMO-2024-001", csa),
        ("ben@demo-university.edu", "Ben Student", m.Role.STUDENT, "DEMO-2024-002", csa),
        ("cara@demo-university.edu", "Cara Student", m.Role.STUDENT, "DEMO-2024-003", csb),
    ]

    for email, display_name, role, student_no, cls in demo_users:
        user = db.scalar(select(m.User).where(m.User.email == email))
        if user is None:
            user = m.User(email=email, password_hash=sec.hash_password(DEMO_PASSWORD))
            db.add(user)
            db.flush()
            created["users"] += 1
        else:
            user.password_hash = sec.hash_password(DEMO_PASSWORD)
            user.is_active = True
        if user.profile is None:
            db.add(m.Profile(user_id=user.id, display_name=display_name))
        ident = db.scalar(
            select(m.UniversityIdentity).where(
                m.UniversityIdentity.user_id == user.id,
                m.UniversityIdentity.university_id == uni.id,
            )
        )
        if ident is None:
            db.add(
                m.UniversityIdentity(
                    user_id=user.id,
                    university_id=uni.id,
                    role=role,
                    status=m.IdentityStatus.VERIFIED,
                    student_no=student_no,
                    class_id=cls.id if cls else None,
                    verified_at=_utcnow(),
                )
            )
        else:
            ident.role = role
            ident.status = m.IdentityStatus.VERIFIED
            ident.student_no = student_no
            ident.class_id = cls.id if cls else None
            if ident.verified_at is None:
                ident.verified_at = _utcnow()

    db.commit()
    return created


def main() -> None:
    db = get_session_factory()()
    try:
        created = seed(db)
        print(f"Seed complete: {created}. Demo password for all users: {DEMO_PASSWORD}")
        print(f"Demo enrollment code for self-registration: {DEMO_ENROLLMENT_CODE}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
