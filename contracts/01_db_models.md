# Контракт 01 — db_models

Файл: `src/core/db/models.py`. ORM: SQLAlchemy 2.x, `DeclarativeBase`. БД: SQLite (`sqlite:///./vpn_panel.db`).

```python
from datetime import datetime
from sqlalchemy import ForeignKey, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(64))              # "Вася", "мой ноут" — для админа
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vless: Mapped["VlessAccount | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    hysteria2: Mapped["Hysteria2Account | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    naive: Mapped["NaiveAccount | None"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")

class VlessAccount(Base):
    __tablename__ = "vless_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    uuid: Mapped[str] = mapped_column(String(36))                # клиентский UUID v4
    short_id: Mapped[str] = mapped_column(String(16))            # Reality short_id, hex, 8-16 симв.
    user: Mapped["User"] = relationship(back_populates="vless")

class Hysteria2Account(Base):
    __tablename__ = "hysteria2_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    password: Mapped[str] = mapped_column(String(64))
    user: Mapped["User"] = relationship(back_populates="hysteria2")

class NaiveAccount(Base):
    __tablename__ = "naive_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    username: Mapped[str] = mapped_column(String(32))
    password: Mapped[str] = mapped_column(String(64))            # plain, нужен как есть для Caddyfile basicauth-хеша при рендере
    user: Mapped["User"] = relationship(back_populates="naive")

class ServerConfig(Base):
    """Singleton: ровно одна строка с id=1."""
    __tablename__ = "server_config"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    domain: Mapped[str] = mapped_column(String(255))              # example.com — для Naive и Reality-фасада
    admin_domain: Mapped[str] = mapped_column(String(255))        # panel.example.com
    admin_username: Mapped[str] = mapped_column(String(32))
    admin_password_hash: Mapped[str] = mapped_column(String(128)) # bcrypt-хеш, для Caddy basicauth
    reality_dest: Mapped[str] = mapped_column(String(255))        # напр. "www.microsoft.com:443"
    reality_private_key: Mapped[str] = mapped_column(String(64))
    reality_public_key: Mapped[str] = mapped_column(String(64))
    reality_short_ids_seed: Mapped[str] = mapped_column(String(16), default="")  # не обязателен, шорт-иды берутся из VlessAccount
```

## Инварианты

- `ServerConfig` — всегда ровно одна строка (`id=1`), создаётся один раз через `POST /api/setup`, дальше только `PATCH`.
- `VlessAccount.uuid` — валидный UUID v4, уникален глобально (проверка на уровне `core/keys`, не БД-констрейнтом — не критично при таком масштабе).
- `NaiveAccount.password` хранится в открытом виде намеренно: Caddyfile-рендеру (`04_render_caddy`) нужен либо plain пароль (Caddy сам хеширует при `basicauth` через `caddy hash-password` во время рендера), либо заранее посчитанный хеш — решение остаётся за `04`, но модель хранит plain, чтобы не зависеть от выбора.
- Удаление `User` каскадно удаляет все три аккаунта (`cascade="all, delete-orphan"`).

## Что нужно от `02_key_generation`

Функции создания записей `VlessAccount`/`Hysteria2Account`/`NaiveAccount` принимают только `user_id` и генерируют остальные поля — модели сами по себе не содержат логики генерации.
