from fastapi import APIRouter

from app.router.calendar import router as calendar_router
from app.router.health import router as health_router
from app.router.hearing import router as hearing_router
from app.router.oauth import oauth_router
from app.router.proposal import router as proposal_router
from app.router.sparring import router as sparring_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(hearing_router)
api_router.include_router(sparring_router)
api_router.include_router(proposal_router)

api_router.include_router(calendar_router)
api_router.include_router(oauth_router)
