"""Тесты web-админки (ТЗ 09).

Маршруты веб-слоя — тонкая обёртка над сервисными функциями `src/api/users.py`,
поэтому используется тот же подход, что и в `tests/api/test_users.py`: in-memory
SQLite, подмена путей конфигов на ``tmp_path`` и мок `core.svc.control.control`.
Реальный ``systemctl`` и боевая БД не затрагиваются.
"""

from __future__ import annotations

import subprocess
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.users import get_db
from src.core import config
from src.core.db.models import Base, User
from src.main import app
from src.web.routes import _links_with_qr


@pytest.fixture
def db_session_factory():
    """In-memory SQLite engine с общей схемой в рамках одного соединения."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Подменить боевые пути конфигов на ``tmp_path``."""
    singbox_path = tmp_path / "sing-box.json"
    caddy_path = tmp_path / "Caddyfile"
    monkeypatch.setattr(config, "SINGBOX_CONFIG_PATH", str(singbox_path))
    monkeypatch.setattr(config, "CADDYFILE_PATH", str(caddy_path))
    return {"singbox": singbox_path, "caddy": caddy_path}


def _successful_control() -> subprocess.CompletedProcess:
    """CompletedProcess с нулевым returncode (успешный reload)."""
    return subprocess.CompletedProcess(
        args=["sudo", "systemctl", "reload", "service"],
        returncode=0,
        stdout=b"",
        stderr=b"",
    )


@pytest.fixture
def control_calls(monkeypatch) -> list[tuple[str, str]]:
    """Мок `core.svc.control.control`: записывает вызовы и возвращает успех."""
    calls: list[tuple[str, str]] = []

    def fake_control(service: str, action: str) -> subprocess.CompletedProcess:
        calls.append((service, action))
        return _successful_control()

    monkeypatch.setattr("src.core.svc.control.control", fake_control)
    return calls


@pytest.fixture
def client(db_session_factory, paths, control_calls) -> Generator[TestClient, None, None]:
    """TestClient с тестовой БД; apply реальный, но control замокан, пути — tmp_path."""

    def override_get_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def _setup_payload() -> dict[str, str]:
    """Валидное тело для `POST /api/setup`."""
    return {
        "domain": "example.com",
        "admin_domain": "panel.example.com",
        "admin_username": "admin",
        "admin_password_hash": "$2b$12$hash",
        "reality_dest": "www.microsoft.com:443",
    }


def _create_user(client: TestClient, label: str = "Вася") -> dict[str, object]:
    """Создать пользователя через API и вернуть его детальное представление."""
    client.post("/api/setup", json=_setup_payload())
    response = client.post("/api/users", json={"label": label})
    assert response.status_code == 201
    return response.json()


def test_index_lists_users_with_status_and_actions(client: TestClient) -> None:
    """`GET /` рендерит всех пользователей, их статус и кнопки действий."""
    _create_user(client, "Вася")

    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert "Вася" in html
    assert "активен" in html
    assert "Выключить" in html
    assert "Удалить" in html
    assert "/users/1" in html


def test_index_empty_state(client: TestClient) -> None:
    """`GET /` без пользователей рендерит пустое состояние."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Пользователей пока нет" in response.text


def test_new_user_form_has_single_label_field(client: TestClient) -> None:
    """`GET /users/new` отдаёт форму с одним полем ``label``."""
    response = client.get("/users/new")
    assert response.status_code == 200
    html = response.text

    assert 'name="label"' in html
    assert "required" in html


def test_create_user_redirects_303_to_detail(
    client: TestClient, db_session_factory, control_calls: list[tuple[str, str]]
) -> None:
    """`POST /users/new` создаёт пользователя и редиректит на `/users/{id}` (303)."""
    client.post("/api/setup", json=_setup_payload())
    control_calls.clear()

    response = client.post("/users/new", data={"label": "Петя"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/users/1"

    db = db_session_factory()
    try:
        user = db.scalars(select(User)).one()
        assert user.label == "Петя"
        assert user.is_active is True
    finally:
        db.close()

    assert control_calls == [("sing-box", "reload"), ("caddy", "reload")]


def test_user_detail_shows_links_and_qr_codes(client: TestClient) -> None:
    """`GET /users/{id}` показывает только не-`None` ссылки и QR-код на каждую."""
    _create_user(client, "Вася")

    response = client.get("/users/1")
    assert response.status_code == 200
    html = response.text

    assert "VLESS" in html
    assert "Hysteria2" in html
    assert "NaiveProxy" in html
    assert "vless://" in html
    assert "hysteria2://" in html
    assert "naive+https://" in html
    assert "<svg" in html
    assert "Копировать" in html
    assert "Выключить" in html
    assert "Удалить" in html


def test_user_detail_missing_returns_404(client: TestClient) -> None:
    """`GET /users/{id}` по несуществующему id → 404."""
    response = client.get("/users/999")
    assert response.status_code == 404


def test_toggle_user_switches_active_state(
    client: TestClient, db_session_factory, control_calls: list[tuple[str, str]]
) -> None:
    """`POST /users/{id}/toggle` переключает `is_active` и редиректит обратно."""
    _create_user(client, "Вася")
    control_calls.clear()

    response = client.post("/users/1/toggle", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/users/1"

    db = db_session_factory()
    try:
        assert db.get(User, 1).is_active is False
    finally:
        db.close()
    assert control_calls == [("sing-box", "reload"), ("caddy", "reload")]


def test_delete_user_redirects_to_index(
    client: TestClient, db_session_factory
) -> None:
    """`POST /users/{id}/delete` удаляет пользователя и редиректит на список."""
    _create_user(client, "Вася")

    response = client.post("/users/1/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    db = db_session_factory()
    try:
        assert db.scalars(select(User)).all() == []
    finally:
        db.close()


def test_links_with_qr_skips_none_links() -> None:
    """`_links_with_qr` возвращает только не-`None` ссылки с SVG-кодом QR."""
    from src.api.schemas import UserDetailOut

    detail = UserDetailOut(
        id=1,
        label="Вася",
        is_active=True,
        created_at="2026-09-13T00:00:00",
        vless_link=None,
        hysteria2_link="hysteria2://password@example.com:443/#Вася",
        naive_link=None,
    )

    items = _links_with_qr(detail)

    assert [item["name"] for item in items] == ["Hysteria2"]
    assert items[0]["link"] == "hysteria2://password@example.com:443/#Вася"
    assert items[0]["qr"].startswith("<svg")