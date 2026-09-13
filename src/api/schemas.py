"""Pydantic-схемы для API (схемы запросов/ответов API пользователей)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServerConfigCreate(BaseModel):
    """Тело `POST /api/setup`.

    Reality-ключи не принимаются: они генерируются сервером один раз при setup.
    """

    domain: str = Field(min_length=1, max_length=255)
    admin_domain: str = Field(min_length=1, max_length=255)
    admin_username: str = Field(min_length=1, max_length=32)
    admin_password_hash: str = Field(min_length=1, max_length=128)
    reality_dest: str = Field(min_length=1, max_length=255)


class ServerConfigOut(BaseModel):
    """Текущий `ServerConfig` без приватного Reality-ключа."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: str
    admin_domain: str
    admin_username: str
    admin_password_hash: str
    reality_dest: str
    reality_public_key: str
    reality_short_ids_seed: str


class UserCreate(BaseModel):
    """Тело `POST /api/users`."""

    label: str = Field(min_length=1, max_length=64)


class UserPatch(BaseModel):
    """Тело `PATCH /api/users/{id}`."""

    is_active: bool


class UserOut(BaseModel):
    """Списочное представление пользователя — без приватных полей аккаунтов."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    is_active: bool
    created_at: datetime


class VlessAccountOut(BaseModel):
    """Приватные поля VLESS-аккаунта (только в детальном ответе)."""

    model_config = ConfigDict(from_attributes=True)

    uuid: str
    short_id: str


class Hysteria2AccountOut(BaseModel):
    """Приватные поля Hysteria2-аккаунта (только в детальном ответе)."""

    model_config = ConfigDict(from_attributes=True)

    password: str


class NaiveAccountOut(BaseModel):
    """Приватные поля NaiveProxy-аккаунта (только в детальном ответе)."""

    model_config = ConfigDict(from_attributes=True)

    username: str
    password: str


class UserDetailOut(UserOut):
    """Детальное представление пользователя: аккаунты + ссылки для копирования."""

    vless: VlessAccountOut | None = None
    hysteria2: Hysteria2AccountOut | None = None
    naive: NaiveAccountOut | None = None
    vless_link: str | None = None
    hysteria2_link: str | None = None
    naive_link: str | None = None