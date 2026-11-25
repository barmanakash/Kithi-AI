from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Bullet = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=300)]


class TailorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=40)
    improve_bullets: bool = False


class CoverLetterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=40)
    tone: Literal["professional", "warm", "concise"] = "professional"


class BulletsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bullets: list[Bullet] = Field(min_length=1, max_length=8)
    job_id: str | None = Field(default=None, max_length=40)
    target_role: str | None = Field(default=None, max_length=150)


class VersionUpdate(BaseModel):
    """Edit a saved draft. `summary` applies to tailored resumes, `text` to cover letters."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=150)
    summary: str | None = Field(default=None, max_length=1000)
    text: str | None = Field(default=None, min_length=1, max_length=8000)

    @model_validator(mode="after")
    def _something_to_change(self):
        if self.title is None and self.summary is None and self.text is None:
            raise ValueError("Nothing to update")
        return self
