"""SQLAlchemy ORM-модели панели : пользователи, аккаунты протоколов, конфигурация сервера.

Модели не содержат логики генерации значений (UUID, ключи, пароли) — эти поля
принимаются как обычные параметры конструктора. Генерация — зона `02_key_generation`.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс декларативных моделей SQLAlchemy 2.x."""


class User(Base):
    """Пользователь панели.

    При создании панель заводит все три аккаунта (VLESS/Hysteria2/Naive).
    Отключение — `is_active = False`, пользователь пропадает из следующего рендера.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vless: Mapped["VlessAccount | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    hysteria2: Mapped["Hysteria2Account | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    naive: Mapped["NaiveAccount | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class VlessAccount(Base):
    """VLESS+Reality аккаунт пользователя."""

    __tablename__ = "vless_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    uuid: Mapped[str] = mapped_column(String(36))
    short_id: Mapped[str] = mapped_column(String(16))
    user: Mapped["User"] = relationship(back_populates="vless")


class Hysteria2Account(Base):
    """Hysteria2 аккаунт пользователя."""

    __tablename__ = "hysteria2_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    password: Mapped[str] = mapped_column(String(64))
    user: Mapped["User"] = relationship(back_populates="hysteria2")


class NaiveAccount(Base):
    """NaiveProxy аккаунт пользователя.

    `password` хранится в открытом виде намеренно: Caddyfile-рендеру
    (`04_render_caddy`) нужен либо plain-пароль, либо заранее посчитанный хеш.
    Модель хранит plain, чтобы не зависеть от выбора рендера.
    """

    __tablename__ = "naive_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    username: Mapped[str] = mapped_column(String(32))
    password: Mapped[str] = mapped_column(String(64))
    user: Mapped["User"] = relationship(back_populates="naive")


class ServerConfig(Base):
    """Singleton-конфигурация сервера: ровно одна строка с `id=1`.

    Инвариант "ровно одна строка" обеспечивается на двух уровнях:
    - на уровне БД: `id` — PRIMARY KEY, поэтому повторный insert с `id=1`
      падает с `IntegrityError` (UNIQUE-констрейнт первичного ключа);
    - на уровне бизнес-логики: строка создаётся один раз через `POST /api/setup`,
      дальше только `PATCH` — это зона `06_api_users_crud`.
    """

    __tablename__ = "server_config"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    domain: Mapped[str] = mapped_column(String(255))
    admin_domain: Mapped[str] = mapped_column(String(255))
    admin_username: Mapped[str] = mapped_column(String(32))
    admin_password_hash: Mapped[str] = mapped_column(String(128))
    reality_dest: Mapped[str] = mapped_column(String(255))
    reality_private_key: Mapped[str] = mapped_column(String(64))
    reality_public_key: Mapped[str] = mapped_column(String(64))
    reality_short_ids_seed: Mapped[str] = mapped_column(String(16), default="")