from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.core.constants import APPLICATION_STATUSES


class RecruiterInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    linkedin_url: HttpUrl | None = None


def _valid_status(value: str) -> str:
    if value not in APPLICATION_STATUSES:
        raise ValueError(f"Status must be one of: {', '.join(APPLICATION_STATUSES)}")
    return value


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    job_url: HttpUrl | None = None
    job_id: str | None = Field(default=None, max_length=24)
    status: str = "saved"
    application_date: date | None = None
    resume_version_id: str | None = Field(default=None, max_length=24)
    cover_letter_version_id: str | None = Field(default=None, max_length=24)
    recruiter: RecruiterInfo | None = None
    follow_up_date: date | None = None
    notes: str = Field(default="", max_length=5000)
    # Required when status is "applied": the user states they submitted it themselves.
    confirmed_by_user: bool = False

    _status = field_validator("status")(_valid_status)


class ApplicationUpdate(BaseModel):
    """Partial update. Only fields that are sent are changed; an explicit null clears optional fields."""

    model_config = ConfigDict(extra="forbid")

    company: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    job_url: HttpUrl | None = None
    application_date: date | None = None
    resume_version_id: str | None = Field(default=None, max_length=24)
    cover_letter_version_id: str | None = Field(default=None, max_length=24)
    recruiter: RecruiterInfo | None = None
    follow_up_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("company", "job_title", "notes", mode="before")
    @classmethod
    def _not_null(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} cannot be cleared")
        return value


class StatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    note: str | None = Field(default=None, max_length=500)
    confirmed_by_user: bool = False

    _status = field_validator("status")(_valid_status)


GenerateKind = Literal["resume", "cover_letter"]
Tone = Literal["professional", "friendly", "confident"]


class GenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=24)
    kinds: list[GenerateKind] = Field(default_factory=lambda: ["resume", "cover_letter"], min_length=1, max_length=2)
    tone: Tone = "professional"
    application_id: str | None = Field(default=None, max_length=24)


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    content_markdown: str | None = Field(default=None, min_length=1, max_length=60000)
