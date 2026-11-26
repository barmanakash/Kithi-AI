from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_current_user
from app.graph.orchestrator import run_coach
from app.services.tasks import record_task

router = APIRouter(prefix="/coach", tags=["coach"])


class Turn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1000)


class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=6)


@router.post("/chat")
def chat(body: ChatIn, user: dict = Depends(get_current_user)) -> dict:
    """Ask the AI Career Coach. A LangGraph router sends your message to the right agent."""
    result = run_coach(user, body.message.strip(), [t.model_dump() for t in body.history])
    record_task(user["_id"], "career_coach", "completed", f"Intent: {result['intent']}")
    return result
