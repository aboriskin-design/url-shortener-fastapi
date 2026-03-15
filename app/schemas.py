from datetime import datetime
from pydantic import BaseModel, HttpUrl, field_validator


class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: str | None = None
    expires_at: datetime | None = None

    @field_validator("custom_alias")
    @classmethod
    def validate_alias(cls, v: str | None):
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3:
            raise ValueError("alias слишком короткий")
        if len(v) > 32:
            raise ValueError("alias слишком длинный")
        # простая проверка: буквы/цифры/_/-
        for ch in v:
            ok = ch.isalnum() or ch in ("_", "-")
            if not ok:
                raise ValueError("alias может содержать только буквы/цифры/_/-")
        return v


class LinkCreateResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime | None = None
    expires_at: datetime | None = None

class LinkStatsResponse(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime | None = None
    clicks: int
    last_accessed_at: datetime | None = None
    expires_at: datetime | None = None

from pydantic import BaseModel, HttpUrl

class LinkUpdate(BaseModel):
    original_url: HttpUrl

class LinkSearchItem(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime | None = None
    expires_at: datetime | None = None

class ExpiredLinkItem(BaseModel):
    short_code: str
    original_url: str
    deleted_reason: str
    deleted_at: datetime | None = None

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"