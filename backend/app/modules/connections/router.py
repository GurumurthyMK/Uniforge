"""Connections API."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.db.session import get_db
from app.modules.connections import schemas as cs
from app.modules.connections import service as svc
from app.modules.identity import models as im
from app.modules.identity.deps import get_current_user

router = APIRouter(tags=["connections"])


@router.get("/connections", response_model=list[cs.ConnectionUserOut])
def list_my_connections(
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> list[cs.ConnectionUserOut]:
    return svc.list_connections(db, user)


@router.get("/connections/requests/incoming", response_model=list[cs.ConnectionUserOut])
def list_incoming(
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> list[cs.ConnectionUserOut]:
    return svc.list_incoming(db, user)


@router.get("/connections/requests/outgoing", response_model=list[cs.ConnectionUserOut])
def list_outgoing(
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> list[cs.ConnectionUserOut]:
    return svc.list_outgoing(db, user)


@router.get("/connections/{user_id}/status", response_model=cs.ConnectionStatusOut)
def get_conn_status(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> cs.ConnectionStatusOut:
    return svc.get_status(db, user, user_id)


@router.get("/connections/{user_id}/mutuals", response_model=cs.MutualsOut)
def get_mutuals(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> cs.MutualsOut:
    return svc.mutual_connections(db, user, user_id)


@router.post("/connections/{user_id}/request", response_model=cs.ConnectionOut, status_code=201)
def request_connection(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> cs.ConnectionOut:
    conn = svc.send_request(db, user, user_id)
    return conn


@router.post("/connections/{user_id}/accept", response_model=cs.ConnectionOut)
def accept_connection(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> cs.ConnectionOut:
    conn = svc.accept_request(db, user, user_id)
    return conn


@router.post("/connections/{user_id}/reject", response_model=cs.ConnectionOut)
def reject_connection(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> cs.ConnectionOut:
    conn = svc.reject_request(db, user, user_id)
    return conn


@router.delete("/connections/{user_id}/request", status_code=204)
def cancel_connection(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> None:
    svc.cancel_request(db, user, user_id)
    return None


@router.delete("/connections/{user_id}", status_code=204)
def remove_connection(
    user_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> None:
    svc.remove_connection(db, user, user_id)
    return None
