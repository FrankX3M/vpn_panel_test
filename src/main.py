"""Точка входа FastAPI (собирает роуты приложения)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.users import router as users_router
from src.core.apply import ApplyError
from src.core.db.session import init_db
from src.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Создаёт таблицы в БД при старте приложения, если их ещё нет (идемпотентно —
    # Base.metadata.create_all не трогает уже существующие таблицы). Без этого вызова
    # любой первый запрос к чистой БД падает с sqlalchemy.exc.OperationalError:
    # no such table — что и происходило на реальном деплое.
    init_db()
    yield


app = FastAPI(title="VPN Panel", lifespan=lifespan)
app.include_router(users_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")


@app.exception_handler(ApplyError)
async def apply_error_handler(request: Request, exc: ApplyError) -> JSONResponse:
    """Вернуть 500 с текстом ошибки применения (stderr systemctl) админу."""
    return JSONResponse(status_code=500, content={"detail": str(exc)})