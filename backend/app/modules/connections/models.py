"""Connection domain model: relational foundation for the network graph.

One row per student pair (directed for request tracking, but unordered uniqueness
enforced at the service layer to prevent A->B and B->A as separate rows).
Statuses: PENDING, ACCEPTED, REJECTED. Cancellation/removal = DELETE (row removed),
REJECTED persists to record the decision; a new request after REJECTED deletes
the old row and creates a fresh PENDING.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConnectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (
        CheckConstraint("requester_id != recipient_id", name="ck_connections_no_self"),
        Index("ix_connections_requester_id", "requester_id"),
        Index("ix_connections_recipient_id", "recipient_id"),
        Index("ix_connections_status", "status"),
        # Unique per directed pair; unordered uniqueness enforced at service layer
        Index("uq_connections_pair", "requester_id", "recipient_id", unique=True),
        # Composite for common lookup patterns
        Index("ix_connections_pair_status", "requester_id", "recipient_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    recipient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[ConnectionStatus] = mapped_column(
        Enum(ConnectionStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ConnectionStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
