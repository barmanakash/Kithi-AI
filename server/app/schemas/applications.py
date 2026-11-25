from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

from app.core.constants import APPLICATION_STATUSES

ApplicationStatus = Literal[tuple(APPLICATION_STATUSES)]


class RecruiterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    linkedin_url: HttpUrl | None = None


def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


class ApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    job_url: HttpUrl | None = None
    job_id: str | None = Field(default=None, max_length=40)
    resume_id: str | None = Field(default=None, max_length=40)
    status: ApplicationStatus = "saved"
    application_date: date | None = None
    follow_up_date: date | None = None
    recruiter: RecruiterIn | None = None
    notes: str = Field(default="", max_length=5000)
    cover_note: str = Field(default="", max_length=5000)

    _blank = field_validator("job_url", "job_id", "resume_id", "application_date", "follow_up_date", mode="before")(
        _blank_to_none
    )

    @field_validator("company", "job_title")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ApplicationUpdate(BaseModel):
    """Partial update: only fields that are sent are changed."""

    model_config = ConfigDict(extra="forbid")

    company: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    job_url: HttpUrl | None = None
    resume_id: str | None = Field(default=None, max_length=40)
    status: ApplicationStatus | None = None
    application_date: date | None = None
    follow_up_date: date | None = None
    recruiter: RecruiterIn | None = None
    notes: str | None = Field(default=None, max_length=5000)
    cover_note: str | None = Field(default=None, max_length=5000)

    _blank = field_validator("job_url", "resume_id", "application_date", "follow_up_date", mode="before")(
        _blank_to_none
    )


class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=500)
