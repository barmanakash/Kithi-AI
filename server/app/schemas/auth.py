from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def _password_rules(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes")
    if not (any(c.isalpha() for c in value) and any(c.isdigit() for c in value)):
        raise ValueError("Password must contain both letters and numbers")
    return value


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=120)

    _check_password = field_validator("password")(_password_rules)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    created_at: datetime


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(description='Must be the exact text "DELETE"')
