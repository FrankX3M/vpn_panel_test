"""Тесты ORM-моделей и инициализации схемы (ТЗ 01).

Используются только временные/in-memory БД — боевая `vpn_panel.db` не затрагивается.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.db import session as session_module
from src.core.db.models import (
    Base,
    Hysteria2Account,
    NaiveAccount,
    ServerConfig,
    User,
    VlessAccount,
)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """In-memory SQLite с общей схемой, видимой в рамках одного соединения."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_user_with_accounts(session: Session) -> User:
    """Создать пользователя со всеми тремя аккаунтами и закоммитить."""
    user = User(label="Вася")
    user.vless = VlessAccount(uuid="11111111-1111-4111-8111-111111111111", short_id="abcd1234")
    user.hysteria2 = Hysteria2Account(password="hy2-secret")
    user.naive = NaiveAccount(username="vasya", password="naive-secret")
    session.add(user)
    session.commit()
    return user


def test_user_is_active_defaults_to_true(db_session: Session) -> None:
    """User без явного is_active получает True."""
    user = User(label="без флага")
    db_session.add(user)
    db_session.commit()

    assert user.is_active is True


def test_cascade_delete_removes_all_accounts(db_session: Session) -> None:
    """Удаление User каскадно удаляет VLESS/Hysteria2/Naive аккаунты."""
    user = _make_user_with_accounts(db_session)
    user_id = user.id

    db_session.delete(user)
    db_session.commit()

    assert db_session.query(VlessAccount).filter_by(user_id=user_id).count() == 0
    assert db_session.query(Hysteria2Account).filter_by(user_id=user_id).count() == 0
    assert db_session.query(NaiveAccount).filter_by(user_id=user_id).count() == 0


def test_server_config_duplicate_id_raises_integrity_error(db_session: Session) -> None:
    """Второй insert ServerConfig с id=1 падает (PRIMARY KEY уникален)."""
    db_session.add(_server_config())
    db_session.commit()

    db_session.add(_server_config())
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def _server_config() -> ServerConfig:
    """Собрать валидный ServerConfig с id=1."""
    return ServerConfig(
        id=1,
        domain="example.com",
        admin_domain="panel.example.com",
        admin_username="admin",
        admin_password_hash="$2b$12$hash",
        reality_dest="www.microsoft.com:443",
        reality_private_key="priv",
        reality_public_key="pub",
    )


def test_init_db_creates_all_tables(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """init_db() создаёт файл БД и все таблицы на чистой базе."""
    db_path = tmp_path / "vpn_panel.db"
    temp_engine = create_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(session_module, "engine", temp_engine)

    session_module.init_db()

    assert db_path.exists()
    tables = set(inspect(temp_engine).get_table_names())
    assert {
        "users",
        "vless_accounts",
        "hysteria2_accounts",
        "naive_accounts",
        "server_config",
    } <= tables
    temp_engine.dispose()