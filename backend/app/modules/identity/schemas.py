"""Pydantic schemas for the identity domain. All external input validated here."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.identity.models import IdentityStatus, Role

PASSWORD_MIN_LENGTH = 8


def _normalize_email(value: str) -> str:
    return value.strip().lower()


class UniversityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    email_domain: str
    city: str | None
    country: str | None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    university_id: uuid.UUID
    name: str
    code: str


class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department_id: uuid.UUID
    name: str
    code: str
    degree_level: str | None


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    program_id: uuid.UUID
    name: str
    start_year: int | None


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    batch_id: uuid.UUID
    name: str
    code: str
    batch_name: str | None = None
    program_name: str | None = None
    department_name: str | None = None


class RegisterIn(BaseModel):
    """Registration collects enough to anchor the student in the university
    structure: university + class + student number + enrollment code."""

    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    university_id: uuid.UUID
    class_id: uuid.UUID
    student_no: str = Field(min_length=1, max_length=50)
    enrollment_code: str = Field(min_length=1, max_length=100)

    _norm_email = field_validator("email", mode="before")(_normalize_email)

    @field_validator("student_no")
    @classmethod
    def _strip_student_no(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("student_no must not be blank")
        return v

    @field_validator("display_name")
    @classmethod
    def _strip_display_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("display_name must not be blank")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    _norm_email = field_validator("email", mode="before")(_normalize_email)


class IdentityOut(BaseModel):
    """VERIFIED university identity — read-only for students."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    university_id: uuid.UUID
    university_name: str | None = None
    role: Role
    status: IdentityStatus
    student_no: str | None
    class_id: uuid.UUID | None
    class_name: str | None = None
    photo_url: str | None = None  # university-controlled photo; admin-written only
    verified_at: datetime | None


class ProfileOut(BaseModel):
    """STUDENT-CONTROLLED profile — editable by the student."""

    model_config = ConfigDict(from_attributes=True)

    display_name: str | None
    bio: str | None


class ProfileUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    bio: str | None = Field(default=None, max_length=2000)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("display_name must not be blank")
        return v.strip() if v is not None else None


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    profile: ProfileOut
    identities: list[IdentityOut]


class SessionOut(BaseModel):
    token: str
    expires_at: datetime


class AuthOut(BaseModel):
    """Returned by register/login: token + expiry + full account snapshot."""

    token: str
    expires_at: datetime
    user: MeOut


class AdminIdentityUpdateIn(BaseModel):
    """University-admin action on an identity. Students can never call this."""

    model_config = ConfigDict(extra="forbid")

    status: IdentityStatus | None = None
    role: Role | None = None
    photo_url: str | None = None

    @field_validator("status")
    @classmethod
    def _no_pending(cls, v: IdentityStatus | None) -> IdentityStatus | None:
        if v == IdentityStatus.PENDING:
            raise ValueError("cannot move an identity back to PENDING")
        return v


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
