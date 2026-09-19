"""Profile + directory + minimal structure-admin API."""

import uuid

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session as DbSession

from app.db.session import get_db
from app.modules.identity import models as im
from app.modules.identity.deps import get_current_user
from app.modules.profile import schemas as ps
from app.modules.profile import service as psvc

router = APIRouter(tags=["profile"])


# ---- Own profile ----


@router.get("/profile/me", response_model=ps.ProfileMeOut)
def get_my_profile(
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> ps.ProfileMeOut:
    return psvc.my_profile(db, user)


@router.patch("/profile/me", response_model=ps.ProfileMeOut)
def update_my_profile(
    data: ps.ProfileEditIn,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> ps.ProfileMeOut:
    return psvc.update_my_profile(db, user, data)


# ---- Public profiles (verified same-university users only) ----


@router.get("/profile/users/{user_id}", response_model=ps.PublicProfileOut)
def get_public_profile(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> ps.PublicProfileOut:
    return psvc.public_profile(db, caller, user_id)


# ---- Class context ----


@router.get("/directory/classes/{class_id}", response_model=ps.ClassDetailOut)
def get_class(
    class_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> ps.ClassDetailOut:
    return psvc.class_detail(db, caller, class_id)


@router.get("/directory/classes/{class_id}/members", response_model=ps.PageOut)
def list_class_members(
    class_id: uuid.UUID,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> ps.PageOut:
    return psvc.class_members(db, caller, class_id, limit, offset)


# ---- Academic structure ----


@router.get("/directory/universities/{university_id}/structure", response_model=ps.StructureOut)
def get_structure(
    university_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    caller: im.User = Depends(get_current_user),
) -> ps.StructureOut:
    return psvc.structure(db, caller, university_id)


# ---- Minimal structure admin (create + rename; no delete in the MVP) ----


@router.post("/admin/structure/universities/{university_id}/departments", status_code=201)
def admin_create_department(
    university_id: uuid.UUID,
    data: ps.DepartmentCreateIn,
    db: DbSession = Depends(get_db),
    admin: im.User = Depends(get_current_user),
) -> dict:
    dept = psvc.admin_create_department(db, admin, university_id, data)
    return {"id": str(dept.id), "name": dept.name, "code": dept.code}


@router.post("/admin/structure/departments/{department_id}/programs", status_code=201)
def admin_create_program(
    department_id: uuid.UUID,
    data: ps.ProgramCreateIn,
    db: DbSession = Depends(get_db),
    admin: im.User = Depends(get_current_user),
) -> dict:
    prog = psvc.admin_create_program(db, admin, department_id, data)
    return {"id": str(prog.id), "name": prog.name, "code": prog.code}


@router.post("/admin/structure/programs/{program_id}/batches", status_code=201)
def admin_create_batch(
    program_id: uuid.UUID,
    data: ps.BatchCreateIn,
    db: DbSession = Depends(get_db),
    admin: im.User = Depends(get_current_user),
) -> dict:
    batch = psvc.admin_create_batch(db, admin, program_id, data)
    return {"id": str(batch.id), "name": batch.name}


@router.post("/admin/structure/batches/{batch_id}/classes", status_code=201)
def admin_create_class(
    batch_id: uuid.UUID,
    data: ps.ClassCreateIn,
    db: DbSession = Depends(get_db),
    admin: im.User = Depends(get_current_user),
) -> dict:
    cls = psvc.admin_create_class(db, admin, batch_id, data)
    return {"id": str(cls.id), "name": cls.name, "code": cls.code}


@router.patch("/admin/structure/{kind}/{item_id}")
def admin_rename(
    data: ps.StructureUpdateIn,
    kind: str = Path(pattern="^(department|program|batch|class)$"),
    item_id: uuid.UUID = Path(),
    db: DbSession = Depends(get_db),
    admin: im.User = Depends(get_current_user),
) -> dict:
    result = psvc.admin_rename(db, admin, kind, item_id, data)
    return {"id": str(result["id"]), "name": result["name"]}
