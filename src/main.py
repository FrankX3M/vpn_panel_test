"""Точка входа FastAPI (собирает роуты приложения)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.users import router as users_router
from src.core.apply import ApplyError
from src.web.routes import router as web_router

app = FastAPI(title="VPN Panel")
app.include_router(users_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")


@app.exception_handler(ApplyError)
async def apply_error_handler(request: Request, exc: ApplyError) -> JSONResponse:
    """Вернуть 500 с текстом ошибки применения (stderr systemctl) админу."""
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# `init_db()` намеренно НЕ вызывается здесь: приложение должно уметь стартовать
# и тестироваться без создания боевой `vpn_panel.db`. Инициализация схемы БД —
# зона боевого запуска (отдельный шаг развёртывания / ТЗ 09).