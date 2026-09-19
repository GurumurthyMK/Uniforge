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
from app.modules.profile import models as pm

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
            db.flush()
        _enrich_demo_profile(db, user, email)
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


DEMO_SKILLS = ["python", "typescript", "machine-learning", "public-speaking", "sql", "ui-design"]
DEMO_INTERESTS = ["robotics", "chess", "photography", "hiking", "open-source"]
DEMO_HOBBIES = ["cycling", "baking", "gaming"]

# email -> (headline, bio, github, linkedin, career, research, skills, interests, hobbies)
DEMO_PROFILES: dict[str, tuple] = {
    "ada@demo-university.edu": (
        "CS undergrad into robotics",
        "Second-year CS student. I build small robots and like clean APIs.",
        "https://github.com/ada-demo",
        "https://linkedin.com/in/ada-demo",
        "Robotics software, backend engineering",
        "Human-robot interaction",
        ["python", "machine-learning", "sql"],
        ["robotics", "open-source"],
        ["cycling"],
    ),
    "ben@demo-university.edu": (
        "Frontend enthusiast",
        "CS student focused on accessible web interfaces.",
        None,
        None,
        "Frontend engineering, design systems",
        None,
        ["typescript", "ui-design"],
        ["photography"],
        ["gaming", "baking"],
    ),
    "cara@demo-university.edu": (
        "Data-curious BSc student",
        "Love turning messy datasets into clear stories.",
        "https://github.com/cara-demo",
        None,
        "Data analysis",
        "Visual analytics",
        ["python", "sql", "public-speaking"],
        ["chess"],
        ["hiking"],
    ),
    "rep@demo-university.edu": (
        "Class rep for CS-2024-A",
        "Your point of contact for class forums and events.",
        None,
        None,
        "Community building",
        None,
        ["public-speaking"],
        ["open-source"],
        [],
    ),
}


def _enrich_demo_profile(db, user: m.User, email: str) -> None:
    """Idempotent demo content: catalog rows + profile fields + edges."""
    for name in DEMO_SKILLS:
        if db.scalar(select(pm.Skill).where(pm.Skill.name == name)) is None:
            db.add(pm.Skill(name=name))
    for name in DEMO_INTERESTS:
        row = db.scalar(select(pm.Interest).where(pm.Interest.name == name))
        if row is None:
            db.add(pm.Interest(name=name, kind=pm.InterestKind.INTEREST.value))
    for name in DEMO_HOBBIES:
        row = db.scalar(select(pm.Interest).where(pm.Interest.name == name))
        if row is None:
            db.add(pm.Interest(name=name, kind=pm.InterestKind.HOBBY.value))
    db.flush()

    spec = DEMO_PROFILES.get(email)
    if spec is None:
        return
    headline, bio, github, linkedin, career, research, skills, interests, hobbies = spec
    profile = user.profile
    if profile is None:  # pragma: no cover - created by caller
        return
    profile.headline = profile.headline or headline
    profile.bio = profile.bio or bio
    profile.github_url = profile.github_url or github
    profile.linkedin_url = profile.linkedin_url or linkedin
    profile.career_interests = profile.career_interests or career
    profile.research_interests = profile.research_interests or research
    for name in skills:
        skill = db.scalar(select(pm.Skill).where(pm.Skill.name == name))
        if db.scalar(
            select(pm.ProfileSkill).where(pm.ProfileSkill.user_id == user.id, pm.ProfileSkill.skill_id == skill.id)
        ) is None:
            db.add(pm.ProfileSkill(user_id=user.id, skill_id=skill.id, source="seed"))
    for name in interests + hobbies:
        interest = db.scalar(select(pm.Interest).where(pm.Interest.name == name))
        if db.scalar(
            select(pm.ProfileInterest).where(
                pm.ProfileInterest.user_id == user.id, pm.ProfileInterest.interest_id == interest.id
            )
        ) is None:
            db.add(pm.ProfileInterest(user_id=user.id, interest_id=interest.id, source="seed"))


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
