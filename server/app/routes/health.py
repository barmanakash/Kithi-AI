from fastapi import APIRouter

from app.core.config import get_settings
from app.database.mongo import ping
from app.utils.helpers import utcnow

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    db_ok = ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "database": {"connected": db_ok, "name": settings.mongodb_db},
        "time": utcnow().isoformat(),
    }
