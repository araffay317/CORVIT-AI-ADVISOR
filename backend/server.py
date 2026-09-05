"""Main FastAPI application server for Corvit AI Advisor."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.routes.health import router as health_router
from backend.routes.chat import router as chat_router
from backend.routes.recommend import router as recommend_router
from backend.routes.dataset_info import router as dataset_info_router

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("corvit_advisor")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan context."""
    logger.info("Starting Corvit AI Advisor API Server...")
    logger.info(f"Primary AI Model: {settings.PRIMARY_MODEL}")
    logger.info(f"Fallback AI Model: {settings.FALLBACK_MODEL}")
    logger.info(f"Allowed CORS Origins: {settings.cors_origins_list}")
    yield
    logger.info("Shutting down Corvit AI Advisor API Server...")


def create_app() -> FastAPI:
    """Application factory for Corvit AI Advisor."""
    app = FastAPI(
        title="Corvit AI Advisor API",
        version="1.0.0",
        description=(
            "Official AI advisory backend for Corvit Systems, providing grounded guidance "
            "on IT courses, curriculum outlines, fees, timetables, and NAVTTC programs."
        ),
        lifespan=lifespan
    )

    # Configure CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=r"^https://([a-zA-Z0-9_-]+\.)?netlify\.app$",
        allow_credentials=True,
        allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
        allow_headers=["*"],
    )

    # Global Exception Handler (prevents leaking internal stack traces for unexpected exceptions)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=getattr(exc, "headers", None)
            )
        logger.error(f"Unhandled server error on {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later."
            }
        )

    # Root Endpoint
    @app.get("/", tags=["Root"])
    async def get_root():
        return {
            "message": "Corvit AI Advisor API is active and running",
            "version": "1.0.0",
            "docs": "/docs"
        }

    # Mount Routers
    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(recommend_router)
    app.include_router(dataset_info_router)

    return app


# Export the app instance for Uvicorn
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.server:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True
    )
