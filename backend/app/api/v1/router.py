from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.crawl import router as crawl_router
from app.api.v1.leads import router as leads_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.analytics import router as analytics_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(crawl_router)
api_router.include_router(leads_router)
api_router.include_router(jobs_router)
api_router.include_router(campaigns_router)
api_router.include_router(analytics_router)


