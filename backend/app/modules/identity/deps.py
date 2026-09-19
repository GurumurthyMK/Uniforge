"""Auth dependencies: current user + server-side role guards.

Every protected endpoint depends on these. The frontend never authorizes.
"""

from fastapi import Depends, status
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as DbSession

from app.db.session import get_db
from app.modules.identity import models as m
from app.modules.identity import service as svc

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")


def get_current_user(
    db: DbSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> m.User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    user = svc.get_session_user(db, credentials.credentials)
    if user is None:
        raise _unauthorized()
    return user


def get_verified_identity(user: m.User, university_id: object) -> m.UniversityIdentity | None:
    for ident in user.identities:
        if ident.university_id == university_id and ident.status == m.IdentityStatus.VERIFIED:
            return ident
    return None
