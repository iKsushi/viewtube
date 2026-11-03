from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

CATEGORIES = [
    "Другое",
    "Технологии",
    "Образование",
    "Музыка",
    "Путешествия",
    "Игры",
    "Кино",
    "Наука",
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Register(Input):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=60)


class Login(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class VideoInput(Input):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=5000)
    category: str = "Другое"
    visibility: Literal["public", "private"] = "public"

    @field_validator("category")
    @classmethod
    def category_valid(cls, value):
        if value not in CATEGORIES:
            raise ValueError("Неизвестная категория")
        return value


class ReactionInput(Input):
    value: Literal[-1, 0, 1]


class CommentInput(Input):
    text: str = Field(min_length=1, max_length=2000)


class GrantInput(Input):
    email: EmailStr


class ReportInput(Input):
    reason: str = Field(min_length=5, max_length=500)


class ModerationInput(Input):
    action: Literal["hide", "dismiss"]
    reason: str = Field(min_length=5, max_length=500)


class ChannelInput(Input):
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=2000)


class PlaylistInput(Input):
    title: str = Field(min_length=1, max_length=100)
    visibility: Literal["public", "private"] = "public"


class WatchInput(Input):
    position: float = Field(default=0, ge=0, le=86400, allow_inf_nan=False)


class RoleInput(Input):
    role: Literal["user", "moderator", "admin"]
