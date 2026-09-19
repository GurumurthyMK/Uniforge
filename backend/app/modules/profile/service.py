"""Profile/directory service.

Visibility rule for public data: the caller must hold a VERIFIED identity at
the same university as the target. Same-university verified users see the
public profile and class rosters; everyone else gets 403/404. Email and
student_no are never included in public payloads.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession, joinedload

from app.modules.identity import models as im
from app.modules.identity import service as isvc
from app.modules.profile import models as pm
from app.modules.profile import schemas as ps


def _node(id: uuid.UUID, name: str) -> ps.AcademicNodeOut:
    return ps.AcademicNodeOut(id=id, name=name)


def academic_context_for(db: DbSession, ident: im.UniversityIdentity) -> ps.AcademicContextOut | None:
    """Derive verified placement from the identity's class chain (server-side)."""
    uni = db.get(im.University, ident.university_id)
    if uni is None:
        return None
    ctx = ps.AcademicContextOut(university=_node(uni.id, uni.name))
    if ident.class_id is None:
        return ctx
    cls = db.get(im.Class, ident.class_id)
    if cls is None:
        return ctx
    batch = cls.batch
    program = batch.program
    department = program.department
    ctx.class_ = _node(cls.id, cls.name)
    ctx.batch = _node(batch.id, batch.name)
    ctx.program = _node(program.id, program.name)
    ctx.department = _node(department.id, department.name)
    return ctx


def _skills_for(db: DbSession, user_id: uuid.UUID) -> list[str]:
    rows = (
        db.execute(
            select(pm.Skill.name)
            .join(pm.ProfileSkill, pm.ProfileSkill.skill_id == pm.Skill.id)
            .where(pm.ProfileSkill.user_id == user_id)
            .order_by(pm.Skill.name)
        )
        .scalars()
        .all()
    )
    return list(rows)


def _interests_for(db: DbSession, user_id: uuid.UUID) -> list[ps.InterestOut]:
    rows = (
        db.execute(
            select(pm.Interest.name, pm.Interest.kind)
            .join(pm.ProfileInterest, pm.ProfileInterest.interest_id == pm.Interest.id)
            .where(pm.ProfileInterest.user_id == user_id)
            .order_by(pm.Interest.name)
        )
        .all()
    )
    return [ps.InterestOut(name=name, kind=pm.InterestKind(kind)) for name, kind in rows]


def _ensure_profile(db: DbSession, user: im.User) -> im.Profile:
    profile = user.profile
    if profile is None:
        profile = im.Profile(user_id=user.id)
        db.add(profile)
        db.flush()
    return profile


def _primary_identity(user: im.User) -> im.UniversityIdentity | None:
    verified = [i for i in user.identities if i.status == im.IdentityStatus.VERIFIED]
    if verified:
        return sorted(verified, key=lambda i: i.created_at)[0]
    if user.identities:
        return sorted(user.identities, key=lambda i: i.created_at)[0]
    return None


def my_profile(db: DbSession, user: im.User) -> ps.ProfileMeOut:
    profile = user.profile  # read-only: never auto-create on GET
    ident = _primary_identity(user)
    return ps.ProfileMeOut(
        user_id=user.id,
        display_name=profile.display_name if profile else None,
        headline=profile.headline if profile else None,
        bio=profile.bio if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        github_url=profile.github_url if profile else None,
        linkedin_url=profile.linkedin_url if profile else None,
        portfolio_url=profile.portfolio_url if profile else None,
        website_url=profile.website_url if profile else None,
        career_interests=profile.career_interests if profile else None,
        research_interests=profile.research_interests if profile else None,
        skills=_skills_for(db, user.id),
        interests=_interests_for(db, user.id),
        academic_context=academic_context_for(db, ident) if ident else None,
        role=ident.role if ident else None,
        verification_status=ident.status if ident else None,
        photo_url=ident.photo_url if ident else None,
    )


def _sync_skills(db: DbSession, user_id: uuid.UUID, names: list[str]) -> None:
    wanted: set[str] = set(names)
    existing = {s for s in _skills_for(db, user_id)}
    for name in wanted - existing:
        skill = db.scalar(select(pm.Skill).where(pm.Skill.name == name))
        if skill is None:
            skill = pm.Skill(name=name)
            db.add(skill)
            db.flush()
        db.add(pm.ProfileSkill(user_id=user_id, skill_id=skill.id, source="manual"))
    if existing - wanted:
        stale_ids = select(pm.Skill.id).where(pm.Skill.name.in_(existing - wanted))
        db.query(pm.ProfileSkill).filter(
            pm.ProfileSkill.user_id == user_id, pm.ProfileSkill.skill_id.in_(stale_ids)
        ).delete(synchronize_session=False)


def _sync_interests(db: DbSession, user_id: uuid.UUID, interests: list[str], hobbies: list[str]) -> None:
    wanted: dict[str, pm.InterestKind] = {n: pm.InterestKind.INTEREST for n in interests}
    for n in hobbies:
        wanted.setdefault(n, pm.InterestKind.HOBBY)
    current = {i.name: i.kind for i in _interests_for(db, user_id)}
    for name, kind in wanted.items():
        if name in current:
            continue
        row = db.scalar(select(pm.Interest).where(pm.Interest.name == name))
        if row is None:
            row = pm.Interest(name=name, kind=kind.value)
            db.add(row)
            db.flush()
        db.add(pm.ProfileInterest(user_id=user_id, interest_id=row.id, source="manual"))
    stale = set(current) - set(wanted)
    if stale:
        stale_ids = select(pm.Interest.id).where(pm.Interest.name.in_(stale))
        db.query(pm.ProfileInterest).filter(
            pm.ProfileInterest.user_id == user_id, pm.ProfileInterest.interest_id.in_(stale_ids)
        ).delete(synchronize_session=False)


def update_my_profile(db: DbSession, user: im.User, data: ps.ProfileEditIn) -> ps.ProfileMeOut:
    """Writes ONLY student-controlled columns + taxonomy edges. Verified
    identity columns are not reachable here by construction."""
    profile = _ensure_profile(db, user)
    for field in (
        "display_name",
        "headline",
        "bio",
        "avatar_url",
        "github_url",
        "linkedin_url",
        "portfolio_url",
        "website_url",
        "career_interests",
        "research_interests",
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(profile, field, value)
    db.add(profile)
    if data.skills is not None:
        _sync_skills(db, user.id, data.skills)
    if data.interests is not None or data.hobbies is not None:
        _sync_interests(
            db,
            user.id,
            data.interests if data.interests is not None else [i.name for i in _interests_for(db, user.id) if i.kind == pm.InterestKind.INTEREST],
            data.hobbies if data.hobbies is not None else [i.name for i in _interests_for(db, user.id) if i.kind == pm.InterestKind.HOBBY],
        )
    db.commit()
    # Re-load user graph for the response.
    db.refresh(user)
    return my_profile(db, user)


def _same_university_verified(caller: im.User, target_university_id: uuid.UUID) -> bool:
    return any(
        i.university_id == target_university_id and i.status == im.IdentityStatus.VERIFIED
        for i in caller.identities
    )


def public_profile(db: DbSession, caller: im.User, target_user_id: uuid.UUID) -> ps.PublicProfileOut:
    target = db.get(im.User, target_user_id)
    if target is None or not target.is_active:
        raise isvc.NotFoundError("Profile not found.")
    ident = _primary_identity(target)
    if ident is None:
        raise isvc.NotFoundError("Profile not found.")
    if not _same_university_verified(caller, ident.university_id):
        raise isvc.ForbiddenError("Only verified members of the same university can view this profile.")
    profile = target.profile
    return ps.PublicProfileOut(
        user_id=target.id,
        display_name=profile.display_name if profile else None,
        headline=profile.headline if profile else None,
        bio=profile.bio if profile else None,
        avatar_url=profile.avatar_url if profile else None,
        github_url=profile.github_url if profile else None,
        linkedin_url=profile.linkedin_url if profile else None,
        portfolio_url=profile.portfolio_url if profile else None,
        website_url=profile.website_url if profile else None,
        career_interests=profile.career_interests if profile else None,
        research_interests=profile.research_interests if profile else None,
        skills=_skills_for(db, target.id),
        interests=_interests_for(db, target.id),
        academic_context=academic_context_for(db, ident),
        role=ident.role,
        verification_status=ident.status,
    )


def class_detail(db: DbSession, caller: im.User, class_id: uuid.UUID) -> ps.ClassDetailOut:
    cls = db.get(im.Class, class_id)
    if cls is None:
        raise isvc.NotFoundError("Class not found.")
    batch, program, department, university = cls.batch, cls.batch.program, cls.batch.program.department, cls.batch.program.department.university
    if not _same_university_verified(caller, university.id):
        raise isvc.ForbiddenError("Only verified members of the same university can view this class.")
    member_count = (
        db.scalar(
            select(func.count())
            .select_from(im.UniversityIdentity)
            .where(
                im.UniversityIdentity.class_id == cls.id,
                im.UniversityIdentity.status == im.IdentityStatus.VERIFIED,
            )
        )
        or 0
    )
    rep_row = (
        db.execute(
            select(im.UniversityIdentity, im.User, im.Profile)
            .join(im.User, im.User.id == im.UniversityIdentity.user_id)
            .outerjoin(im.Profile, im.Profile.user_id == im.User.id)
            .where(
                im.UniversityIdentity.class_id == cls.id,
                im.UniversityIdentity.role == im.Role.CLASS_REP,
                im.UniversityIdentity.status == im.IdentityStatus.VERIFIED,
            )
            .order_by(im.UniversityIdentity.created_at)
        )
        .first()
    )
    rep = None
    if rep_row is not None:
        _, rep_user, rep_profile = rep_row
        rep = ps.ClassMemberOut(
            user_id=rep_user.id,
            display_name=rep_profile.display_name if rep_profile else None,
            role=im.Role.CLASS_REP,
            verification_status=im.IdentityStatus.VERIFIED,
        )
    return ps.ClassDetailOut(
        **{
            "class": _node(cls.id, cls.name),
            "batch": _node(batch.id, batch.name),
            "program": _node(program.id, program.name),
            "department": _node(department.id, department.name),
            "university": _node(university.id, university.name),
            "member_count": member_count,
            "class_rep": rep,
        }
    )


def class_members(
    db: DbSession, caller: im.User, class_id: uuid.UUID, limit: int, offset: int
) -> ps.PageOut:
    detail = class_detail(db, caller, class_id)  # reuses visibility check
    _ = detail
    base = (
        select(im.UniversityIdentity, im.Profile)
        .outerjoin(im.Profile, im.Profile.user_id == im.UniversityIdentity.user_id)
        .where(
            im.UniversityIdentity.class_id == class_id,
            im.UniversityIdentity.status == im.IdentityStatus.VERIFIED,
        )
        .order_by(im.UniversityIdentity.created_at)
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(im.UniversityIdentity)
            .where(
                im.UniversityIdentity.class_id == class_id,
                im.UniversityIdentity.status == im.IdentityStatus.VERIFIED,
            )
        )
        or 0
    )
    rows = db.execute(base.limit(limit).offset(offset)).all()
    return ps.PageOut(
        items=[
            ps.ClassMemberOut(
                user_id=ident.user_id,
                display_name=prof.display_name if prof else None,
                role=ident.role,
                verification_status=ident.status,
            )
            for ident, prof in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def structure(db: DbSession, caller: im.User, university_id: uuid.UUID) -> ps.StructureOut:
    uni = db.get(im.University, university_id)
    if uni is None:
        raise isvc.NotFoundError("University not found.")
    if not _same_university_verified(caller, university_id):
        raise isvc.ForbiddenError("Only verified members of this university can view its structure.")
    counts = dict(
        db.execute(
            select(
                im.UniversityIdentity.class_id,
                func.count(im.UniversityIdentity.id),
            )
            .where(im.UniversityIdentity.status == im.IdentityStatus.VERIFIED)
            .group_by(im.UniversityIdentity.class_id)
        ).all()
    )
    departments = (
        db.execute(select(im.Department).where(im.Department.university_id == uni.id).order_by(im.Department.name))
        .scalars()
        .all()
    )
    dept_out: list[ps.StructureDepartmentOut] = []
    for dept in departments:
        prog_out: list[ps.StructureProgramOut] = []
        programs = (
            db.execute(select(im.Program).where(im.Program.department_id == dept.id).order_by(im.Program.name))
            .scalars()
            .all()
        )
        for prog in programs:
            batch_out: list[ps.StructureBatchOut] = []
            batches = (
                db.execute(select(im.Batch).where(im.Batch.program_id == prog.id).order_by(im.Batch.name))
                .scalars()
                .all()
            )
            for batch in batches:
                classes = (
                    db.execute(select(im.Class).where(im.Class.batch_id == batch.id).order_by(im.Class.name))
                    .scalars()
                    .all()
                )
                batch_out.append(
                    ps.StructureBatchOut(
                        id=batch.id,
                        name=batch.name,
                        start_year=batch.start_year,
                        classes=[
                            ps.StructureClassOut(
                                id=c.id, name=c.name, code=c.code, member_count=counts.get(c.id, 0)
                            )
                            for c in classes
                        ],
                    )
                )
            prog_out.append(
                ps.StructureProgramOut(
                    id=prog.id, name=prog.name, code=prog.code, degree_level=prog.degree_level, batches=batch_out
                )
            )
        dept_out.append(ps.StructureDepartmentOut(id=dept.id, name=dept.name, code=dept.code, programs=prog_out))
    return ps.StructureOut(university_id=uni.id, university_name=uni.name, departments=dept_out)


def _require_admin(db: DbSession, admin: im.User, university_id: uuid.UUID) -> None:
    # Refresh identities to ensure current roles (detached instances in tests).
    db.refresh(admin, attribute_names=["identities"])
    if not isvc.is_admin_of(admin, university_id):
        raise isvc.ForbiddenError("Admin rights at this university are required.")


def _university_of_department(db: DbSession, department_id: uuid.UUID) -> im.Department:
    dept = db.get(im.Department, department_id)
    if dept is None:
        raise isvc.NotFoundError("Department not found.")
    return dept


def admin_create_department(db: DbSession, admin: im.User, university_id: uuid.UUID, data: ps.DepartmentCreateIn) -> im.Department:
    uni = db.get(im.University, university_id)
    if uni is None:
        raise isvc.NotFoundError("University not found.")
    _require_admin(db, admin, university_id)
    dept = im.Department(university_id=uni.id, name=data.name.strip(), code=data.code.strip())
    db.add(dept)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise isvc.ConflictError("A department with this code already exists.")
    db.refresh(dept)
    return dept


def admin_create_program(db: DbSession, admin: im.User, department_id: uuid.UUID, data: ps.ProgramCreateIn) -> im.Program:
    dept = _university_of_department(db, department_id)
    _require_admin(db, admin, dept.university_id)
    prog = im.Program(
        department_id=dept.id, name=data.name.strip(), code=data.code.strip(), degree_level=data.degree_level
    )
    db.add(prog)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise isvc.ConflictError("A program with this code already exists.")
    db.refresh(prog)
    return prog


def admin_create_batch(db: DbSession, admin: im.User, program_id: uuid.UUID, data: ps.BatchCreateIn) -> im.Batch:
    prog = db.get(im.Program, program_id)
    if prog is None:
        raise isvc.NotFoundError("Program not found.")
    _require_admin(db, admin, prog.department.university_id)
    batch = im.Batch(program_id=prog.id, name=data.name.strip(), start_year=data.start_year)
    db.add(batch)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise isvc.ConflictError("A batch with this name already exists.")
    db.refresh(batch)
    return batch


def admin_create_class(db: DbSession, admin: im.User, batch_id: uuid.UUID, data: ps.ClassCreateIn) -> im.Class:
    batch = db.get(im.Batch, batch_id)
    if batch is None:
        raise isvc.NotFoundError("Batch not found.")
    _require_admin(db, admin, batch.program.department.university_id)
    cls = im.Class(batch_id=batch.id, name=data.name.strip(), code=data.code.strip())
    db.add(cls)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise isvc.ConflictError("A class with this code already exists.")
    db.refresh(cls)
    return cls


def admin_rename(
    db: DbSession, admin: im.User, kind: str, item_id: uuid.UUID, data: ps.StructureUpdateIn
) -> dict:
    model = {"department": im.Department, "program": im.Program, "batch": im.Batch, "class": im.Class}[kind]
    item = db.get(model, item_id)
    if item is None:
        raise isvc.NotFoundError(f"{kind.capitalize()} not found.")
    if kind == "department":
        university_id = item.university_id
    elif kind == "program":
        university_id = item.department.university_id
    elif kind == "batch":
        university_id = item.program.department.university_id
    else:
        university_id = item.batch.program.department.university_id
    _require_admin(db, admin, university_id)
    if data.name is not None:
        item.name = data.name.strip()
    if data.code is not None and hasattr(item, "code"):
        item.code = data.code.strip()
    if data.degree_level is not None and hasattr(item, "degree_level"):
        item.degree_level = data.degree_level
    if data.start_year is not None and hasattr(item, "start_year"):
        item.start_year = data.start_year
    db.add(item)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise isvc.ConflictError("An item with this code/name already exists.")
    db.refresh(item)
    return {"id": item.id, "name": item.name}
