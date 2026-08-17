import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from services.api.config import get_settings
from database.postgres.connection import init_db
from services.api.routers import (
    auth,
    tenants,
    documents,
    regulations,
    policies,
    compliance,
    workflows,
    approvals,
    audit,
)

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database schemas...")
    await init_db()
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} initialized successfully.")
    yield
    # Shutdown
    logger.info("Shutting down platform...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Multi-Tenant AI Compliance & Bank Policy Platform",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Modular Sub-Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tenants.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(regulations.router, prefix="/api/v1")
app.include_router(policies.router, prefix="/api/v1")
app.include_router(compliance.router, prefix="/api/v1")
app.include_router(workflows.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")


@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "neo4j_mode": "mock" if settings.NEO4J_MOCK_MODE else "connected",
    }


# Mount static files for frontend if directory exists
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
