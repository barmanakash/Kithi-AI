from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator

from app.agents.job_analysis import DEFAULT_WEIGHTS

JobSource = Literal["remotive", "arbeitnow"]


class JobIn(BaseModel):
    """A job the user adds manually (pasted from a posting)."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    company: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    remote: bool = False
    job_type: str | None = Field(default=None, max_length=40)
    url: HttpUrl | None = None
    salary_text: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=20, max_length=30000)


class DiscoverIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=2, max_length=100)
    location: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=15, ge=1, le=30)
    sources: list[JobSource] = Field(default_factory=lambda: ["remotive", "arbeitnow"], min_length=1, max_length=2)


class MatchWeightsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skills: float = Field(default=DEFAULT_WEIGHTS["skills"], ge=0, le=100)
    experience: float = Field(default=DEFAULT_WEIGHTS["experience"], ge=0, le=100)
    responsibilities: float = Field(default=DEFAULT_WEIGHTS["responsibilities"], ge=0, le=100)
    education: float = Field(default=DEFAULT_WEIGHTS["education"], ge=0, le=100)
    location: float = Field(default=DEFAULT_WEIGHTS["location"], ge=0, le=100)
    preferences: float = Field(default=DEFAULT_WEIGHTS["preferences"], ge=0, le=100)

    @model_validator(mode="after")
    def _not_all_zero(self):
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("At least one weight must be greater than zero")
        return self


class ScamAssessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=20, max_length=30000)
    title: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    url: HttpUrl | None = None
    contact_email: EmailStr | None = None
    save: bool = True
