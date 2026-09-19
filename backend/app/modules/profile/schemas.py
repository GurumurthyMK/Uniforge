"""Pydantic schemas for the profile/directory domain.

Boundary rule: ProfileEditIn contains ONLY student-controlled fields and
forbids extras. There is no schema, endpoint, or code path through which a
student can write university-controlled columns (student_no, role, status,
class_id, photo_url) — those live exclusively in the admin API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter, field_validator

from app.modules.identity.models import IdentityStatus, Role
from app.modules.profile.models import InterestKind

MAX_URL_LEN = 500
MAX_SKILLS = 20
MAX_INTERESTS = 20
MAX_HOBBIES = 20

_http_url = TypeAdapter(HttpUrl)


def _optional_url(v: str | None, field: str) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v:
        return None
    if len(v) > MAX_URL_LEN:
        raise ValueError(f"{field} must be at most {MAX_URL_LEN} characters")
    try:
        return str(_http_url.validate_python(v))
    except Exception:
        raise ValueError(f"{field} must be a valid http(s) URL")


def _name_list(v: list[str] | None, field: str, limit: int) -> list[str]:
    items = v or []
    if len(items) > limit:
        raise ValueError(f"at most {limit} {field} allowed")
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in items:
        name = raw.strip().lower()
        if not name or name in seen:
            continue
        if len(name) > 100:
            raise ValueError(f"each {field} must be at most 100 characters")
        seen.add(name)
        cleaned.append(name)
    return cleaned


class ProfileEditIn(BaseModel):
    """Student-controlled fields ONLY. Unknown fields are rejected (422)."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    headline: str | None = Field(default=None, max_length=150)
    bio: str | None = Field(default=None, max_length=2000)
    avatar_url: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    website_url: str | None = None
    career_interests: str | None = Field(default=None, max_length=2000)
    research_interests: str | None = Field(default=None, max_length=2000)
    skills: list[str] | None = None
    interests: list[str] | None = None
    hobbies: list[str] | None = None

    @field_validator("display_name", "headline", "bio", "career_interests", "research_interests")
    @classmethod
    def _strip_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None

    @field_validator("avatar_url", "github_url", "linkedin_url", "portfolio_url", "website_url")
    @classmethod
    def _check_url(cls, v: str | None, info) -> str | None:
        return _optional_url(v, info.field_name)

    @field_validator("skills")
    @classmethod
    def _check_skills(cls, v: list[str] | None) -> list[str]:
        return _name_list(v, "skills", MAX_SKILLS)

    @field_validator("interests")
    @classmethod
    def _check_interests(cls, v: list[str] | None) -> list[str]:
        return _name_list(v, "interests", MAX_INTERESTS)

    @field_validator("hobbies")
    @classmethod
    def _check_hobbies(cls, v: list[str] | None) -> list[str]:
        return _name_list(v, "hobbies", MAX_HOBBIES)


class InterestOut(BaseModel):
    name: str
    kind: InterestKind


class AcademicNodeOut(BaseModel):
    id: uuid.UUID
    name: str


class AcademicContextOut(BaseModel):
    """Verified academic placement, derived server-side from the identity's
    class chain. Read-only for students."""

    university: AcademicNodeOut
    department: AcademicNodeOut | None = None
    program: AcademicNodeOut | None = None
    batch: AcademicNodeOut | None = None
    class_: AcademicNodeOut | None = Field(default=None, alias="class")

    model_config = ConfigDict(populate_by_name=True)


class ProfileMeOut(BaseModel):
    user_id: uuid.UUID
    display_name: str | None
    headline: str | None
    bio: str | None
    avatar_url: str | None
    github_url: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    website_url: str | None
    career_interests: str | None
    research_interests: str | None
    skills: list[str]
    interests: list[InterestOut]
    academic_context: AcademicContextOut | None
    role: Role | None
    verification_status: IdentityStatus | None
    photo_url: str | None = None  # university-controlled photo, if set


class PublicProfileOut(BaseModel):
    """What other verified university users may see. No email, no student_no."""

    user_id: uuid.UUID
    display_name: str | None
    headline: str | None
    bio: str | None
    avatar_url: str | None
    github_url: str | None
    linkedin_url: str | None
    portfolio_url: str | None
    website_url: str | None
    career_interests: str | None
    research_interests: str | None
    skills: list[str]
    interests: list[InterestOut]
    academic_context: AcademicContextOut | None
    role: Role
    verification_status: IdentityStatus


class ClassMemberOut(BaseModel):
    user_id: uuid.UUID
    display_name: str | None
    role: Role
    verification_status: IdentityStatus


class ClassDetailOut(BaseModel):
    class_: AcademicNodeOut = Field(alias="class")
    batch: AcademicNodeOut
    program: AcademicNodeOut
    department: AcademicNodeOut
    university: AcademicNodeOut
    member_count: int
    class_rep: ClassMemberOut | None = None

    model_config = ConfigDict(populate_by_name=True)


class StructureClassOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    member_count: int


class StructureBatchOut(BaseModel):
    id: uuid.UUID
    name: str
    start_year: int | None
    classes: list[StructureClassOut]


class StructureProgramOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    degree_level: str | None
    batches: list[StructureBatchOut]


class StructureDepartmentOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    programs: list[StructureProgramOut]


class StructureOut(BaseModel):
    university_id: uuid.UUID
    university_name: str
    departments: list[StructureDepartmentOut]


# ---- Minimal admin structure management ----


class DepartmentCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)


class ProgramCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)
    degree_level: str | None = Field(default=None, max_length=50)


class BatchCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    start_year: int | None = Field(default=None, ge=1900, le=2100)


class ClassCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=50)


class StructureUpdateIn(BaseModel):
    """Rename/patch for any structure entity; only applicable fields are used."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    degree_level: str | None = Field(default=None, max_length=50)
    start_year: int | None = Field(default=None, ge=1900, le=2100)


class PageOut(BaseModel):
    items: list[ClassMemberOut]
    total: int
    limit: int
    offset: int
