"""Web admin UI (веб-админка панели).

Тонкая Jinja2-обёртка над сервисными функциями `src/api/users.py`: маршруты
напрямую вызывают те же функции, что и REST API, а не ходят на себя по HTTP.
Аутентификация внутри FastAPI намеренно отсутствует — Basic Auth обеспечивает
Caddy (контракт `04_render_caddy`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.api.schemas import UserCreate, UserDetailOut, UserPatch
from src.api.users import (
    ApplyFunc,
    get_apply,
    get_db,
)
from src.api.users import (
    create_user as api_create_user,
)
from src.api.users import (
    delete_user as api_delete_user,
)
from src.api.users import (
    get_user as api_get_user,
)
from src.api.users import (
    list_users as api_list_users,
)
from src.api.users import (
    patch_user as api_patch_user,
)
from src.core.render.links import qr_svg

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

DB = Annotated[Session, Depends(get_db)]
APPLY = Annotated[ApplyFunc, Depends(get_apply)]


@router.get("/")
def index(request: Request, db: DB) -> Response:
    """Рендер списка всех пользователей с текущим статусом и кнопками действий."""
    users = api_list_users(db)
    return templates.TemplateResponse(request, "index.html", {"users": users})


@router.get("/users/new")
def new_user_form(request: Request) -> Response:
    """Форма создания пользователя: одно поле ``label``."""
    return templates.TemplateResponse(request, "new_user.html")


@router.post("/users/new")
def create_user_view(label: Annotated[str, Form()], db: DB, apply: APPLY) -> RedirectResponse:
    """Создать пользователя через сервисную функцию ТЗ 06 и редиректнуть на карточку."""
    user = api_create_user(UserCreate(label=label), db, apply)
    return RedirectResponse(url=f"/users/{user.id}", status_code=303)


@router.get("/users/{user_id}")
def user_detail(request: Request, user_id: int, db: DB) -> Response:
    """Карточка пользователя: доступные ссылки + QR-код на каждую, кнопки действий."""
    detail = api_get_user(user_id, db)
    links = _links_with_qr(detail)
    return templates.TemplateResponse(
        request,
        "user_detail.html",
        {"user": detail, "links": links},
    )


@router.post("/users/{user_id}/toggle")
def toggle_user(user_id: int, db: DB, apply: APPLY) -> RedirectResponse:
    """Переключить ``is_active`` пользователя и вернуться на его карточку."""
    detail = api_get_user(user_id, db)
    api_patch_user(user_id, UserPatch(is_active=not detail.is_active), db, apply)
    return RedirectResponse(url=f"/users/{user_id}", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user_view(user_id: int, db: DB, apply: APPLY) -> RedirectResponse:
    """Удалить пользователя и вернуться на список."""
    api_delete_user(user_id, db, apply)
    return RedirectResponse(url="/", status_code=303)


def _links_with_qr(detail: UserDetailOut) -> list[dict[str, str]]:
    """Собрать ссылки с инлайн-SVG QR-кодами, пропуская отсутствующие (``None``).

    Аргументы:
        detail: детальное представление пользователя с уже сформированными
            ссылками (см. `08_client_links`).

    Возвращает:
        Список словарей ``{"name", "link", "qr"}`` только по не-``None`` ссылкам.
    """
    items: list[dict[str, str]] = []
    for name, link in (
        ("VLESS", detail.vless_link),
        ("Hysteria2", detail.hysteria2_link),
        ("NaiveProxy", detail.naive_link),
    ):
        if link is not None:
            items.append({"name": name, "link": link, "qr": qr_svg(link)})
    return items