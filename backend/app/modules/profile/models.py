"""Profile taxonomy models: canonical skills/interests + student edges.

These edge tables ARE the future talent graph in relational form:

    Student → HAS_SKILL → Skill        (profile_skills)
    Student → HAS_INTEREST → Interest  (profile_interests, kind=INTEREST/HOBBY)

The `source` column is the extension point for future evidence/import
pipelines ("manual" today; e.g. "import:github", "inferred:project" later)
without any redesign. No graph logic lives here — just clean relational
edges with bounded cardinality enforced at the service layer.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InterestKind(str, enum.Enum):
    INTEREST = "INTEREST"
    HOBBY = "HOBBY"


class Skill(Base):
    """Canonical skill catalog. Names stored normalized (lowercase, trimmed)."""

    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Interest(Base):
    """Canonical interest/hobby catalog. Names stored normalized."""

    __tablename__ = "interests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    kind: Mapped[InterestKind] = mapped_column(
        # Stored as plain string; validated at the service layer.
        String(20),
        nullable=False,
        server_default=InterestKind.INTEREST.value,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProfileSkill(Base):
    """Student → HAS_SKILL → Skill edge."""

    __tablename__ = "profile_skills"
    __table_args__ = (Index("ix_profile_skills_skill_id", "skill_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProfileInterest(Base):
    """Student → HAS_INTEREST → Interest edge."""

    __tablename__ = "profile_interests"
    __table_args__ = (Index("ix_profile_interests_interest_id", "interest_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    interest_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interests.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
