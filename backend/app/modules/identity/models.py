"""Identity domain models.

Two concepts are kept strictly separate:

- VERIFIED UNIVERSITY IDENTITY (university-controlled): University,
  Department, Program, Batch, Class, and UniversityIdentity. Rows here are
  created/approved by university admins or by the demo verification flow
  (enrollment code + email domain). Students cannot self-edit them.
- STUDENT-CONTROLLED PROFILE (Profile): free-form user data. Never treated
  as verified.

Academic hierarchy: University → Department → Program → Batch → Class.
A UniversityIdentity links a User to one University with a Role and an
optional Class (students) — the anchor for all future authorization
(class/forum membership, class-rep powers) and for the network graph.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Role(str, enum.Enum):
    UNIVERSITY_ADMIN = "UNIVERSITY_ADMIN"
    DEPARTMENT_ADMIN = "DEPARTMENT_ADMIN"
    FACULTY = "FACULTY"
    STAFF = "STAFF"
    CLASS_REP = "CLASS_REP"
    STUDENT = "STUDENT"


class IdentityStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class University(Base, TimestampMixin):
    """University-controlled: verified institution record (seeded for the demo)."""

    __tablename__ = "universities"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)  # e.g. "DEMO-U"
    email_domain: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "demo-university.edu"
    # Demo verification secret. Real ERP integration would replace this;
    # possession of the code stands in for university-controlled proof.
    enrollment_code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))

    departments: Mapped[list["Department"]] = relationship(back_populates="university")
    identities: Mapped[list["UniversityIdentity"]] = relationship(back_populates="university")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    university_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("universities.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (
        Index("ix_departments_university_id", "university_id"),
        Index("uq_departments_university_code", "university_id", "code", unique=True),
    )

    university: Mapped[University] = relationship(back_populates="departments")
    programs: Mapped[list["Program"]] = relationship(back_populates="department")


class Program(Base, TimestampMixin):
    __tablename__ = "programs"
    __table_args__ = (
        Index("ix_programs_department_id", "department_id"),
        Index("uq_programs_department_code", "department_id", "code", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    degree_level: Mapped[str | None] = mapped_column(String(50))  # e.g. "BSc", "MSc"

    department: Mapped[Department] = relationship(back_populates="programs")
    batches: Mapped[list["Batch"]] = relationship(back_populates="program")


class Batch(Base, TimestampMixin):
    __tablename__ = "batches"
    __table_args__ = (
        Index("ix_batches_program_id", "program_id"),
        Index("uq_batches_program_name", "program_id", "name", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "2024"
    start_year: Mapped[int | None] = mapped_column()

    program: Mapped[Program] = relationship(back_populates="batches")
    classes: Mapped[list["Class"]] = relationship(back_populates="batch")


class Class(Base, TimestampMixin):
    """A class (cohort section). Class reps are resolved via UniversityIdentity
    (role=CLASS_REP, class_id=X) — no circular FK to users."""

    __tablename__ = "classes"
    __table_args__ = (
        Index("ix_classes_batch_id", "batch_id"),
        Index("uq_classes_batch_code", "batch_id", "code", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g. "CS-2024-A"
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "A"

    batch: Mapped[Batch] = relationship(back_populates="classes")
    identities: Mapped[list["UniversityIdentity"]] = relationship(back_populates="class_")


class User(Base, TimestampMixin):
    """Login account. Holds credentials only — not academic facts."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Stored lowercased; unique index enforces one account per email.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    profile: Mapped["Profile | None"] = relationship(back_populates="user", cascade="all, delete-orphan")
    identities: Mapped[list["UniversityIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Profile(Base, TimestampMixin):
    """STUDENT-CONTROLLED profile. Free-form; never treated as verified."""

    __tablename__ = "profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(back_populates="profile")


class UniversityIdentity(Base, TimestampMixin):
    """VERIFIED UNIVERSITY IDENTITY: links a User to a University.

    Only admins (or the demo verification flow evaluating university-controlled
    data) may create/verify rows. Students must never self-verify.
    """

    __tablename__ = "university_identities"
    __table_args__ = (
        Index("ix_identities_user_id", "user_id"),
        Index("ix_identities_university_id", "university_id"),
        Index("ix_identities_class_id", "class_id"),
        Index("uq_identities_university_student_no", "university_id", "student_no", unique=True),
        CheckConstraint("student_no <> ''", name="ck_identities_student_no_nonempty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    university_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("universities.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, validate_strings=True), nullable=False)
    status: Mapped[IdentityStatus] = mapped_column(
        Enum(IdentityStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=IdentityStatus.PENDING,
    )
    # University-controlled student number, e.g. "DEMO-2024-001".
    student_no: Mapped[str | None] = mapped_column(String(50))
    class_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("classes.id", ondelete="SET NULL"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="identities")
    university: Mapped[University] = relationship(back_populates="identities")
    class_: Mapped["Class | None"] = relationship(back_populates="identities")


class Session(Base):
    """Server-side opaque session. Only a SHA-256 hash of the token is stored;
    the raw token is shown to the client once at login/register."""

    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")
