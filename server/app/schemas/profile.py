from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def year_month():
    return Field(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM")


def short_text(max_length: int = 200):
    return Field(default=None, max_length=max_length)


class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=150)
    location: str | None = short_text()
    start_date: str | None = year_month()
    end_date: str | None = year_month()
    current: bool = False
    description: str = Field(default="", max_length=3000)
    achievements: list[str] = Field(default_factory=list, max_length=20)


class Education(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institution: str = Field(min_length=1, max_length=200)
    degree: str = Field(min_length=1, max_length=150)
    field_of_study: str | None = short_text()
    start_year: int | None = Field(default=None, ge=1950, le=2100)
    end_year: int | None = Field(default=None, ge=1950, le=2100)
    grade: str | None = short_text(50)


class Certification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    issuer: str | None = short_text()
    year: int | None = Field(default=None, ge=1950, le=2100)
    url: HttpUrl | None = None


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=2000)
    technologies: list[str] = Field(default_factory=list, max_length=30)
    url: HttpUrl | None = None


class SalaryExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_amount: float | None = Field(default=None, ge=0)
    max_amount: float | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    period: Literal["annual", "monthly"] = "annual"


EmploymentPreference = Literal[
    "full_time", "part_time", "contract", "internship", "remote", "hybrid", "onsite"
]


def _clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in values:
        item = item.strip()
        if item and item.lower() not in seen:
            seen.add(item.lower())
            cleaned.append(item[:60])
    return cleaned


class CandidateProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = short_text(120)
    headline: str | None = short_text(200)
    summary: str | None = short_text(3000)
    phone: str | None = short_text(30)
    location: str | None = short_text()

    experience: list[Experience] = Field(default_factory=list, max_length=30)
    technical_skills: list[str] = Field(default_factory=list, max_length=100)
    soft_skills: list[str] = Field(default_factory=list, max_length=50)
    education: list[Education] = Field(default_factory=list, max_length=15)
    certifications: list[Certification] = Field(default_factory=list, max_length=30)
    projects: list[Project] = Field(default_factory=list, max_length=30)

    salary_expectation: SalaryExpectation | None = None
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    preferred_locations: list[str] = Field(default_factory=list, max_length=20)
    employment_preferences: list[EmploymentPreference] = Field(default_factory=list)

    linkedin_url: HttpUrl | None = None
    github_url: HttpUrl | None = None
    portfolio_url: HttpUrl | None = None

    _clean_skills = field_validator(
        "technical_skills", "soft_skills", "preferred_locations"
    )(_clean_list)
