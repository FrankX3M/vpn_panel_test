"""Настройка подключения к SQLite и инициализация схемы (контракт `01_db_models.md`)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.db.models import Base

engine = create_engine("sqlite:///./vpn_panel.db")
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """Создать все таблицы в базе, если их ещё нет.

    Вызывается один раз при старте приложения. Ничего не возвращает,
    исключения пробрасывает наружу (ошибки подключения/создания схемы).
    """
    Base.metadata.create_all(engine)