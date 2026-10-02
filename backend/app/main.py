from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.redis_client import close_redis
from app.api.v1.router import api_router
from app.api.v1.health import router as health_router

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("lead_intelligence")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up %s in %s mode...", settings.PROJECT_NAME, settings.ENVIRONMENT)
    yield
    # Shutdown
    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    await close_redis()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception at %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred.", "path": request.url.path},
    )


# Root endpoints
@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "docs_url": f"{settings.API_V1_PREFIX}/docs",
        "health_url": "/health",
    }


# Include root-level /health as well as versioned /api/v1/health
app.include_router(health_router)
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
