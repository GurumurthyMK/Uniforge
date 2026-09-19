"""API v1 router aggregation. Domain routers will be included here."""

from fastapi import APIRouter

from app.api.v1.health import router as health_router
from app.modules.forum.router import router as forum_router
from app.modules.identity.router import router as identity_router
from app.modules.profile.router import router as profile_router

router = APIRouter()
router.include_router(health_router)
router.include_router(identity_router)
router.include_router(profile_router)
router.include_router(forum_router)
