from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.agents.job_analysis import DEFAULT_WEIGHTS
from app.agents.job_discovery import SOURCES

JobType = Literal["full_time", "part_time", "contract", "internship"]


class JobIn(BaseModel):
    """A job the user adds by hand (for example pasted from a site that is not a permitted source)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=20, max_length=30000)
    location: str | None = Field(default=None, max_length=200)
    remote: bool = False
    job_type: JobType | None = None
    url: HttpUrl | None = None
    salary_text: str | None = Field(default=None, max_length=100)

    @field_validator("title", "company")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class DiscoverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=20, ge=1, le=50, description="Maximum jobs requested per source")
    sources: list[str] = Field(default_factory=lambda: list(SOURCES), min_length=1, max_length=10)

    @field_validator("sources")
    @classmethod
    def _known_sources(cls, values: list[str]) -> list[str]:
        unknown = [v for v in values if v not in SOURCES]
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(unknown)}. Allowed: {', '.join(SOURCES)}")
        return list(dict.fromkeys(values))


class WeightsIn(BaseModel):
    """Configurable match weights. Any non-negative numbers; they are re-normalised when scoring."""

    model_config = ConfigDict(extra="forbid")

    skills: float = Field(default=DEFAULT_WEIGHTS["skills"], ge=0, le=100)
    experience: float = Field(default=DEFAULT_WEIGHTS["experience"], ge=0, le=100)
    responsibilities: float = Field(default=DEFAULT_WEIGHTS["responsibilities"], ge=0, le=100)
    education: float = Field(default=DEFAULT_WEIGHTS["education"], ge=0, le=100)
    location: float = Field(default=DEFAULT_WEIGHTS["location"], ge=0, le=100)
    preferences: float = Field(default=DEFAULT_WEIGHTS["preferences"], ge=0, le=100)

    @model_validator(mode="after")
    def _at_least_one(self):
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("At least one weight must be greater than zero")
        return self


class ScamCheckIn(BaseModel):
    """Check pasted text, or a job already saved in the user's pipeline."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, max_length=30000)
    job_id: str | None = Field(default=None, max_length=40)
    company: str | None = Field(default=None, max_length=200)
    url: HttpUrl | None = None
    contact_email: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _needs_input(self):
        if not self.job_id and len((self.text or "").strip()) < 20:
            raise ValueError("Provide the listing text (at least 20 characters) or a job_id")
        return self
