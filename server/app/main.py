"""Kithi AI backend entry point.

Run from the server folder:
    uvicorn app.main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.database.mongo import close_client, init_db, ping
from app.routes import account, ai, applications, auth, career, coach, dashboard, generate, health, interviews, matches, memory, profile, recruiter_messages, recruiters, resumes, salary, scam
from app.routes import jobs as jobs_routes
from app.services.ai_service import AIServiceError, get_ai_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("kithi")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    if ping():
        try:
            init_db()
        except Exception:  # keep the API up so /health can report the problem
            logger.exception("Database initialisation failed")
    else:
        logger.warning(
            "MongoDB is not reachable at %s. Start MongoDB, then restart the API so indexes are created.",
            settings.mongodb_uri,
        )
    yield
    get_ai_service().close()
    close_client()


def create_app() -> FastAPI:
    settings = get_settings()
    dev = settings.environment == "development"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if dev else None,
        redoc_url=None,
        openapi_url="/openapi.json" if dev else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # bearer tokens in the Authorization header, no cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    @app.exception_handler(AIServiceError)
    async def ai_error_handler(_: Request, exc: AIServiceError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    prefix = settings.api_prefix
    for module in (
        health, auth, profile, resumes, ai, account,
        jobs_routes, matches, scam, applications, dashboard, generate,
        recruiters, recruiter_messages, career, memory, interviews, salary, coach,
    ):
        app.include_router(module.router, prefix=prefix)

    return app


app = create_app()
