"""FastAPI-роутер users/setup CRUD (CRUD пользователей и первичная настройка сервера).

Вызов применения конфигов (`core.apply.apply`) подключается через инъекцию
зависимости `get_apply`. Импорт `core.apply` выполняется лениво внутри `get_apply`,
чтобы роутер оставался импортируемым без побочных эффектов применения конфигов.
"""

from collections.abc import Callable, Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import (
    Hysteria2AccountOut,
    NaiveAccountOut,
    ServerConfigCreate,
    ServerConfigOut,
    UserCreate,
    UserDetailOut,
    UserOut,
    UserPatch,
    VlessAccountOut,
)
from src.core.db.models import (
    Hysteria2Account,
    NaiveAccount,
    ServerConfig,
    User,
    VlessAccount,
)
from src.core.db.session import SessionLocal
from src.core.keys import generate
from src.core.render.links import hysteria2_link, naive_link, vless_link

router = APIRouter(prefix="/api")

# Тип функции применения конфигов (`core.apply.apply(session)`), подменяемый
# в тестах через dependency_overrides. Определён заранее, чтобы эндпоинты не
# импортировали `core.apply` напрямую.
ApplyFunc = Callable[[Session], None]


def get_db() -> Generator[Session, None, None]:
    """Отдать SQLAlchemy-сессию и гарантированно закрыть её после запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_apply() -> ApplyFunc:
    """Вернуть реальную функцию применения конфигов.

    Импорт отложен до первого вызова зависимости, чтобы не тянуть `core.apply`
    (и, косвенно, `core.svc`) на этапе импорта роутера. Возвращаемая функция
    имеет сигнатуру `(session: Session) -> None`.
    """
    from src.core.apply import apply

    return apply


DB = Annotated[Session, Depends(get_db)]
APPLY = Annotated[ApplyFunc, Depends(get_apply)]


def _get_user_or_404(session: Session, user_id: int) -> User:
    """Вернуть пользователя по id либо поднять HTTP 404."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _server_config(session: Session) -> ServerConfig | None:
    """Вернуть singleton-строку ServerConfig либо None, если setup ещё не было."""
    return session.get(ServerConfig, 1)


def _build_detail(user: User, server: ServerConfig | None) -> UserDetailOut:
    """Собрать детальное представление пользователя со ссылками на клиент."""
    return UserDetailOut(
        id=user.id,
        label=user.label,
        is_active=user.is_active,
        created_at=user.created_at,
        vless=VlessAccountOut.model_validate(user.vless) if user.vless is not None else None,
        hysteria2=(
            Hysteria2AccountOut.model_validate(user.hysteria2)
            if user.hysteria2 is not None
            else None
        ),
        naive=NaiveAccountOut.model_validate(user.naive) if user.naive is not None else None,
        vless_link=vless_link(user, server) if server is not None else None,
        hysteria2_link=hysteria2_link(user, server) if server is not None else None,
        naive_link=naive_link(user, server) if server is not None else None,
    )


@router.post("/setup", response_model=ServerConfigOut, status_code=status.HTTP_201_CREATED)
def create_server_config(payload: ServerConfigCreate, db: DB) -> ServerConfigOut:
    """Создать singleton-конфигурацию сервера (один раз).

    Reality-ключи генерируются сервером при первом setup. Повторный вызов
    возвращает 409. Применение конфигов здесь не вызывается — мутации,
    требующие apply, это `POST/PATCH/DELETE /api/users`.
    """
    if _server_config(db) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ServerConfig already exists",
        )

    private_key, public_key = generate.new_reality_keypair()
    config = ServerConfig(
        id=1,
        domain=payload.domain,
        admin_domain=payload.admin_domain,
        admin_username=payload.admin_username,
        admin_password_hash=payload.admin_password_hash,
        reality_dest=payload.reality_dest,
        reality_private_key=private_key,
        reality_public_key=public_key,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return ServerConfigOut.model_validate(config)


@router.get("/server-config", response_model=ServerConfigOut)
def get_server_config(db: DB) -> ServerConfigOut:
    """Вернуть текущую конфигурацию сервера без приватного Reality-ключа."""
    config = _server_config(db)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ServerConfig not found",
        )
    return ServerConfigOut.model_validate(config)


@router.post("/users", response_model=UserDetailOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DB, apply: APPLY) -> UserDetailOut:
    """Создать пользователя и три связанных аккаунта, затем применить конфиги."""
    existing_usernames: set[str] = set(db.scalars(select(NaiveAccount.username)).all())

    user = User(label=payload.label)
    user.vless = VlessAccount(
        uuid=generate.new_vless_uuid(),
        short_id=generate.new_reality_short_id(),
    )
    user.hysteria2 = Hysteria2Account(password=generate.new_password())
    user.naive = NaiveAccount(
        username=generate.new_naive_username(payload.label, existing_usernames),
        password=generate.new_password(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    apply(db)

    return _build_detail(user, _server_config(db))


@router.get("/users", response_model=list[UserOut])
def list_users(db: DB) -> list[UserOut]:
    """Вернуть список пользователей без приватных полей аккаунтов."""
    users = db.scalars(select(User).order_by(User.id)).all()
    return [UserOut.model_validate(user) for user in users]


@router.get("/users/{user_id}", response_model=UserDetailOut)
def get_user(user_id: int, db: DB) -> UserDetailOut:
    """Вернуть пользователя с аккаунтами и ссылками (для копирования)."""
    user = _get_user_or_404(db, user_id)
    return _build_detail(user, _server_config(db))


@router.patch("/users/{user_id}", response_model=UserDetailOut)
def patch_user(user_id: int, payload: UserPatch, db: DB, apply: APPLY) -> UserDetailOut:
    """Обновить `is_active` пользователя и применить конфиги."""
    user = _get_user_or_404(db, user_id)
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)

    apply(db)

    return _build_detail(user, _server_config(db))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DB, apply: APPLY) -> Response:
    """Удалить пользователя каскадно со всеми аккаунтами и применить конфиги."""
    user = _get_user_or_404(db, user_id)
    db.delete(user)
    db.commit()

    apply(db)

    return Response(status_code=status.HTTP_204_NO_CONTENT)