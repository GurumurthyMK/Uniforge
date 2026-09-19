"""Pydantic schemas for connections."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.connections.models import ConnectionStatus


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    requester_id: uuid.UUID
    recipient_id: uuid.UUID
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime


class ConnectionUserOut(BaseModel):
    user_id: uuid.UUID
    display_name: str | None
    headline: str | None = None
    avatar_url: str | None = None
    role: str | None = None
    verification_status: str | None = None
    # connection metadata
    connection_id: uuid.UUID | None = None
    status: ConnectionStatus | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConnectionStatusOut(BaseModel):
    status: str  # NONE | PENDING_OUTGOING | PENDING_INCOMING | CONNECTED | REJECTED
    connection: ConnectionOut | None = None


class MutualsOut(BaseModel):
    count: int
    users: list[ConnectionUserOut]
    # also include total mutual count
