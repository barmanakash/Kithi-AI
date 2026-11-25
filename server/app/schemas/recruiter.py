from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator, model_validator

MessageKind = Literal["outreach", "referral", "follow_up", "thank_you", "reply"]
Channel = Literal["email", "linkedin"]
MessageTone = Literal["professional", "warm", "concise"]
MESSAGE_STATUSES = ("draft", "approved", "sent")


def _blank_to_none(value):
    return None if isinstance(value, str) and not value.strip() else value


class RecruiterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=150)
    linkedin_url: HttpUrl | None = None
    notes: str = Field(default="", max_length=2000)

    _blank = field_validator("email", "phone", "company", "title", "linkedin_url", mode="before")(_blank_to_none)

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class RecruiterUpdate(BaseModel):
    """Partial update. Only fields that are sent change; an explicit null clears optional fields."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=150)
    linkedin_url: HttpUrl | None = None
    notes: str | None = Field(default=None, max_length=2000)

    _blank = field_validator("email", "phone", "company", "title", "linkedin_url", mode="before")(_blank_to_none)

    @field_validator("name", "notes", mode="before")
    @classmethod
    def _not_null(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name} cannot be cleared")
        return value


class MessageGenerateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: MessageKind
    channel: Channel = "email"
    tone: MessageTone = "professional"
    recruiter_id: str | None = Field(default=None, max_length=24)
    job_id: str | None = Field(default=None, max_length=24)
    application_id: str | None = Field(default=None, max_length=24)
    # A message you received (untrusted). Used only as context for a reply, never obeyed.
    incoming_message: str | None = Field(default=None, max_length=4000)
    # Your own extra instructions or facts for this message, e.g. "I am available to talk on weekdays".
    note: str | None = Field(default=None, max_length=500)

    _blank = field_validator("recruiter_id", "job_id", "application_id", "incoming_message", "note", mode="before")(_blank_to_none)

    @model_validator(mode="after")
    def _needs_context(self):
        if self.kind == "reply" and not (self.incoming_message or "").strip():
            raise ValueError("Paste the message you received to write a reply")
        if self.kind == "follow_up" and not (self.application_id or self.job_id):
            raise ValueError("Choose the application or job you are following up on")
        if self.kind in ("referral", "thank_you") and not (self.job_id or self.application_id):
            raise ValueError("Choose the job or application this message is about")
        return self


class MessageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, min_length=1, max_length=8000)

    @model_validator(mode="after")
    def _something_to_change(self):
        if self.subject is None and self.body is None:
            raise ValueError("Nothing to update")
        return self


class ApprovalIn(BaseModel):
    """Explicit approval. Anything other than `true` is rejected."""

    model_config = ConfigDict(extra="forbid")

    confirmed_by_user: bool  # required: omitting it is a validation error, and false is rejected below

    @field_validator("confirmed_by_user")
    @classmethod
    def _must_confirm(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("You must explicitly confirm this action")
        return value


class SentIn(ApprovalIn):
    note: str | None = Field(default=None, max_length=300)
