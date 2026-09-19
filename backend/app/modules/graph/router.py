"""Graph API: student-centered bounded network."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.db.session import get_db
from app.modules.graph import schemas as gs
from app.modules.graph import service as gsvc
from app.modules.identity import models as im
from app.modules.identity.deps import get_current_user

router = APIRouter(tags=["graph"])


@router.get("/graph/me", response_model=gs.GraphResponse)
def get_my_graph(
    db: DbSession = Depends(get_db),
    user: im.User = Depends(get_current_user),
) -> gs.GraphResponse:
    return gsvc.build_graph(db, user)
