from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.services.ai_service import get_ai_service
from app.services.prompts import PING_TASK, SYSTEM_BASE

router = APIRouter(prefix="/ai", tags=["ai"])


class _Ping(BaseModel):
    ok: bool = False
    message: str = ""


@router.get("/status")
def ai_status(user: dict = Depends(get_current_user)) -> dict:
    """Reports whether Ollama is running and the configured model is installed."""
    return get_ai_service().status()


@router.post("/ping")
def ai_ping(user: dict = Depends(get_current_user)) -> dict:
    """Runs a tiny structured-output request through the full local AI pipeline."""
    result = get_ai_service().generate_structured(SYSTEM_BASE, PING_TASK, _Ping)
    return result.model_dump()
