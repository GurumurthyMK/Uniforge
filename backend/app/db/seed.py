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
        ("diana@demo-university.edu", "Diana Student", m.Role.STUDENT, "DEMO-2024-004", csa),
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

    _seed_forums(db, csa, csb, uni)
    _seed_discussions(db)
    _seed_connections(db)

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
    "diana@demo-university.edu": (
        "Systems-curious student",
        "Exploring networks and systems design.",
        None,
        None,
        "Systems engineering",
        "Distributed systems",
        ["sql", "python"],
        ["open-source", "photography"],
        ["hiking"],
    ),
}


def _seed_forums(db: Session, csa: m.Class, csb: m.Class, uni) -> None:
    """Seed a few forums: approved + pending + demo memberships (idempotent)."""
    try:
        from app.modules.forum import models as fm  # lazy import to avoid cycle
    except Exception:
        return
    rep = db.scalar(select(m.User).where(m.User.email == "rep@demo-university.edu"))
    ada = db.scalar(select(m.User).where(m.User.email == "ada@demo-university.edu"))
    ben = db.scalar(select(m.User).where(m.User.email == "ben@demo-university.edu"))
    cara = db.scalar(select(m.User).where(m.User.email == "cara@demo-university.edu"))

    specs: list[tuple[m.Class, str, str, fm.ForumStatus, m.User | None]] = [
        (csa, "General Discussion", "Campus-wide chat for CS-2024-A", fm.ForumStatus.APPROVED, ada),
        (csa, "DSA Doubts", "Data structures and algorithms Q&A", fm.ForumStatus.APPROVED, rep),
        (csa, "Project Discussion", "Final year project ideas and teams", fm.ForumStatus.APPROVED, rep),
        (csa, "Resources", "Share notes, links and past papers", fm.ForumStatus.APPROVED, rep),
        (csa, "Exam Prep", "Proposal awaiting rep approval", fm.ForumStatus.PENDING, ada),
        (csb, "General Discussion", "Welcome forum for CS-2024-B", fm.ForumStatus.APPROVED, cara),
    ]
    for cls, name, desc, status, creator in specs:
        existing = db.scalar(select(fm.Forum).where(fm.Forum.class_id == cls.id, fm.Forum.name == name))
        if existing is None:
            f = fm.Forum(
                class_id=cls.id,
                name=name,
                description=desc,
                status=status,
                created_by=creator.id if creator else None,
                approved_by=rep.id if status == fm.ForumStatus.APPROVED and rep else None,
            )
            db.add(f)
            db.flush()
            existing = f
        else:
            # Keep status/description in sync for idempotency, but don't override pending
            if existing.status != status and existing.name != "Exam Prep":
                existing.status = status
                db.add(existing)
        # Demo memberships: ada + ben joined General Discussion (csa)
        if existing.name == "General Discussion" and existing.class_id == csa.id:
            for u in [ada, ben, rep]:
                if u is None:
                    continue
                if (
                    db.scalar(
                        select(fm.ForumMembership).where(
                            fm.ForumMembership.forum_id == existing.id, fm.ForumMembership.user_id == u.id
                        )
                    )
                    is None
                ):
                    db.add(fm.ForumMembership(forum_id=existing.id, user_id=u.id))
        if existing.name == "DSA Doubts" and existing.status == fm.ForumStatus.APPROVED:
            if ada and db.scalar(select(fm.ForumMembership).where(fm.ForumMembership.forum_id == existing.id, fm.ForumMembership.user_id == ada.id)) is None:
                db.add(fm.ForumMembership(forum_id=existing.id, user_id=ada.id))
    db.flush()


def _seed_discussions(db: Session) -> None:
    """Add small realistic discussion data to approved forums (idempotent)."""
    try:
        from app.modules.forum import models as fm
    except Exception:
        return
    # ensure forums exist first
    def _forum(cls_name: str, forum_name: str):
        return db.scalar(
            select(fm.Forum)
            .join(m.Class, m.Class.id == fm.Forum.class_id)
            .where(m.Class.name == cls_name, fm.Forum.name == forum_name)
        )
    rep = db.scalar(select(m.User).where(m.User.email == "rep@demo-university.edu"))
    ada = db.scalar(select(m.User).where(m.User.email == "ada@demo-university.edu"))
    ben = db.scalar(select(m.User).where(m.User.email == "ben@demo-university.edu"))
    # ensure memberships for seed authors
    def _ensure_member(forum, user):
        if forum is None or user is None:
            return
        if db.scalar(select(fm.ForumMembership).where(fm.ForumMembership.forum_id == forum.id, fm.ForumMembership.user_id == user.id)) is None:
            db.add(fm.ForumMembership(forum_id=forum.id, user_id=user.id))
    # define posts per forum: (cls, forum_name) -> list[(author_email, content)]
    posts_spec: dict[tuple[str, str], list[tuple[str, str]]] = {
        ("CS-2024-A", "General Discussion"): [
            ("ada@demo-university.edu", "Hey everyone! Excited for the new semester. Any study group plans?"),
            ("ben@demo-university.edu", "Welcome! I made a shared drive for notes — check the Resources forum."),
            ("rep@demo-university.edu", "Hey folks — class rep here. Ping me for forum proposals or issues."),
            ("ada@demo-university.edu", "Anyone going to the hackathon next weekend?"),
        ],
        ("CS-2024-A", "DSA Doubts"): [
            ("ada@demo-university.edu", "How do we approach graph traversal for the assignment? BFS or DFS?"),
            ("ben@demo-university.edu", "Can someone explain time complexity of quicksort worst case?"),
            ("rep@demo-university.edu", "Resources for DP practice — share your favourite problem sets below."),
            ("ada@demo-university.edu", "Stuck on heap implementation — any pointers?"),
        ],
        ("CS-2024-A", "Project Discussion"): [
            ("ben@demo-university.edu", "Looking for teammates for the robotics project — I do frontend + sensors."),
            ("ada@demo-university.edu", "I can handle backend + ML. Let's team up!"),
            ("rep@demo-university.edu", "Reminder: project proposals due Friday. Use the forum to recruit."),
        ],
        ("CS-2024-A", "Resources"): [
            ("rep@demo-university.edu", "Pinned: past papers and lecture slides -> https://example.com/resources"),
            ("ben@demo-university.edu", "My notes for Algorithms week 3 — hope it helps!"),
        ],
    }
    # quick email -> user map
    users_by_email = {u.email: u for u in db.scalars(select(m.User).where(m.User.email.in_(["rep@demo-university.edu","ada@demo-university.edu","ben@demo-university.edu"]))).all()}
    # create posts idempotently by content prefix match
    for (cls_name, forum_name), posts in posts_spec.items():
        forum = _forum(cls_name, forum_name)
        if forum is None:
            continue
        for email, content in posts:
            user = users_by_email.get(email)
            _ensure_member(forum, user)
            # check existing post with same forum and content prefix
            exists = db.scalar(select(fm.Post).where(fm.Post.forum_id == forum.id, fm.Post.content == content))
            if exists:
                post = exists
            else:
                post = fm.Post(forum_id=forum.id, author_id=user.id if user else None, content=content)
                db.add(post)
                db.flush()
            # add comments/likes for this post
            # comment spec: mapping content prefix -> comments
            # For demo, add a couple comments on first posts
            if post.content.startswith("How do we approach"):
                # comment from ben
                if ben and db.scalar(select(fm.Comment).where(fm.Comment.post_id == post.id, fm.Comment.content == "Try using BFS for shortest path, DFS for connectivity. I can share my notes!")) is None:
                    c = fm.Comment(post_id=post.id, author_id=ben.id, content="Try using BFS for shortest path, DFS for connectivity. I can share my notes!")
                    db.add(c); db.flush()
                    # notification to post author
                    if post.author_id and post.author_id != ben.id:
                        if db.scalar(select(fm.Notification).where(fm.Notification.comment_id == c.id)) is None:
                            db.add(fm.Notification(user_id=post.author_id, actor_id=ben.id, type="COMMENT_ON_POST", post_id=post.id, forum_id=forum.id, comment_id=c.id, message="Someone commented on your post in DSA Doubts"))
                if rep and db.scalar(select(fm.Comment).where(fm.Comment.post_id == post.id, fm.Comment.content == "Office hours tomorrow 4pm — bring your code.")) is None:
                    db.add(fm.Comment(post_id=post.id, author_id=rep.id, content="Office hours tomorrow 4pm — bring your code."))
            if post.content.startswith("Hey everyone"):
                if ben and db.scalar(select(fm.Comment).where(fm.Comment.post_id == post.id, fm.Comment.content == "Count me in! When do we meet?")) is None:
                    db.add(fm.Comment(post_id=post.id, author_id=ben.id, content="Count me in! When do we meet?"))
                if rep and db.scalar(select(fm.Comment).where(fm.Comment.post_id == post.id, fm.Comment.content == "Let's do Thursday library 3pm.")) is None:
                    db.add(fm.Comment(post_id=post.id, author_id=rep.id, content="Let's do Thursday library 3pm."))
            # likes: every post gets likes from other users
            for liker in [ada, ben, rep]:
                if liker is None or liker.id == post.author_id:
                    continue
                # give like to first 2 posts per forum
                if posts.index((email, content)) < 2:
                    if db.scalar(select(fm.PostReaction).where(fm.PostReaction.post_id == post.id, fm.PostReaction.user_id == liker.id)) is None:
                        db.add(fm.PostReaction(post_id=post.id, user_id=liker.id))
    db.flush()


def _seed_connections(db: Session) -> None:
    """Seed realistic connections for UI demo (idempotent)."""
    try:
        from app.modules.connections import models as cm
        from app.modules.forum import models as fm
    except Exception:
        return
    ada = db.scalar(select(m.User).where(m.User.email == "ada@demo-university.edu"))
    ben = db.scalar(select(m.User).where(m.User.email == "ben@demo-university.edu"))
    cara = db.scalar(select(m.User).where(m.User.email == "cara@demo-university.edu"))
    diana = db.scalar(select(m.User).where(m.User.email == "diana@demo-university.edu"))
    if not all([ada, ben, cara, diana]):
        return
    # Desired edges: Ada->Ben ACCEPTED, Ada->Cara ACCEPTED, Ben->Diana ACCEPTED, Cara->Diana PENDING
    specs: list[tuple[m.User, m.User, cm.ConnectionStatus]] = [
        (ada, ben, cm.ConnectionStatus.ACCEPTED),
        (ada, cara, cm.ConnectionStatus.ACCEPTED),
        (ben, diana, cm.ConnectionStatus.ACCEPTED),
        (cara, diana, cm.ConnectionStatus.PENDING),
    ]
    for req, rec, status in specs:
        # check existing in either direction
        existing = db.scalar(
            select(cm.Connection).where(
                ((cm.Connection.requester_id == req.id) & (cm.Connection.recipient_id == rec.id))
                | ((cm.Connection.requester_id == rec.id) & (cm.Connection.recipient_id == req.id))
            )
        )
        if existing is None:
            db.add(cm.Connection(requester_id=req.id, recipient_id=rec.id, status=status))
            db.flush()
            if status == cm.ConnectionStatus.PENDING:
                # notification for recipient
                if db.scalar(select(fm.Notification).where(fm.Notification.user_id == rec.id, fm.Notification.actor_id == req.id, fm.Notification.type == "CONNECTION_REQUEST")) is None:
                    db.add(fm.Notification(user_id=rec.id, actor_id=req.id, type="CONNECTION_REQUEST", message="A student sent you a connection request."))
        else:
            # sync status if mismatched (keep idempotent)
            if existing.status != status:
                # for demo, keep PENDING vs ACCEPTED distinction
                existing.status = status
                db.add(existing)
    db.flush()


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
