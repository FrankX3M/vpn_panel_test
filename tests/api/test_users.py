"""Тесты API users/setup CRUD (ТЗ 06 + интеграция с 07).

Используются `fastapi.testclient.TestClient` и in-memory SQLite — боевая
`vpn_panel.db` не затрагивается. Реальное применение конфигов (`core.apply.apply`)
вызывается с моком `core.svc.control.control`, а пути конфигов подменяются на
``tmp_path`` — реальный ``/etc`` не затрагивается и ``systemctl`` не вызывается.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.users import get_db
from src.core import config
from src.core.db.models import (
    Base,
    Hysteria2Account,
    NaiveAccount,
    User,
    VlessAccount,
)
from src.main import app


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
    """Подменить боевые пути конфигов на ``tmp_path`` и вернуть их для проверок."""
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


def test_setup_twice_returns_409(client: TestClient) -> None:
    """Повторный `POST /api/setup` → 409."""
    first = client.post("/api/setup", json=_setup_payload())
    assert first.status_code == 201

    second = client.post("/api/setup", json=_setup_payload())
    assert second.status_code == 409


def test_create_user_creates_three_accounts(
    client: TestClient, db_session_factory, control_calls: list[tuple[str, str]]
) -> None:
    """`POST /api/users` создаёт User + 3 аккаунта и вызывает apply (control reload)."""
    client.post("/api/setup", json=_setup_payload())

    response = client.post("/api/users", json={"label": "Вася"})
    assert response.status_code == 201
    body = response.json()

    assert body["label"] == "Вася"
    assert body["is_active"] is True
    assert body["vless"]["uuid"] != ""
    assert body["vless"]["short_id"] != ""
    assert body["hysteria2"]["password"] != ""
    assert body["naive"]["username"] != ""
    assert body["naive"]["password"] != ""

    db = db_session_factory()
    try:
        user = db.scalars(select(User)).one()
        assert db.scalars(select(VlessAccount)).one().user_id == user.id
        assert db.scalars(select(Hysteria2Account)).one().user_id == user.id
        assert db.scalars(select(NaiveAccount)).one().user_id == user.id
    finally:
        db.close()

    assert control_calls == [("sing-box", "reload"), ("caddy", "reload")]


def test_create_user_writes_singbox_and_caddy_configs(client: TestClient, paths) -> None:
    """`POST /api/users` записывает валидный sing-box JSON и непустой Caddyfile."""
    client.post("/api/setup", json=_setup_payload())
    created = client.post("/api/users", json={"label": "Вася"}).json()

    singbox = json.loads(paths["singbox"].read_text(encoding="utf-8"))
    inbounds = {item["tag"]: item for item in singbox["inbounds"]}
    vless_uuids = {item["uuid"] for item in inbounds["vless-reality-in"]["users"]}
    assert created["vless"]["uuid"] in vless_uuids

    caddy = paths["caddy"].read_text(encoding="utf-8")
    assert caddy.strip() != ""


def test_create_user_returns_500_when_control_fails(
    client: TestClient, monkeypatch
) -> None:
    """Ошибка reload (ApplyError) → HTTP 500 с текстом stderr в теле ответа."""
    client.post("/api/setup", json=_setup_payload())

    def failing_control(service: str, action: str) -> subprocess.CompletedProcess:
        if service == "caddy":
            raise RuntimeError("invalid Caddyfile")
        return _successful_control()

    monkeypatch.setattr("src.core.svc.control.control", failing_control)

    response = client.post("/api/users", json={"label": "Вася"})
    assert response.status_code == 500
    assert "invalid Caddyfile" in response.json()["detail"]


def test_list_users_has_no_private_account_fields(
    client: TestClient, db_session_factory
) -> None:
    """`GET /api/users` возвращает только id/label/is_active/created_at."""
    client.post("/api/setup", json=_setup_payload())
    client.post("/api/users", json={"label": "Вася"})

    response = client.get("/api/users")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert set(items[0].keys()) == {"id", "label", "is_active", "created_at"}


def test_get_user_detail_includes_accounts_and_links(client: TestClient) -> None:
    """`GET /api/users/{id}` включает приватные поля аккаунтов и ссылки."""
    client.post("/api/setup", json=_setup_payload())
    created = client.post("/api/users", json={"label": "Вася"}).json()

    response = client.get(f"/api/users/{created['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["vless"]["uuid"] != ""
    assert body["hysteria2"]["password"] != ""
    assert body["naive"]["password"] != ""
    assert body["vless_link"].startswith("vless://")
    assert body["hysteria2_link"].startswith("hysteria2://")
    assert body["naive_link"].startswith("naive+https://")


def test_patch_user_updates_is_active(
    client: TestClient, control_calls: list[tuple[str, str]]
) -> None:
    """`PATCH /api/users/{id} {"is_active": false}` обновляет поле и вызывает apply."""
    client.post("/api/setup", json=_setup_payload())
    created = client.post("/api/users", json={"label": "Вася"}).json()
    control_calls.clear()

    response = client.patch(f"/api/users/{created['id']}", json={"is_active": False})
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert control_calls == [("sing-box", "reload"), ("caddy", "reload")]


def test_delete_user_cascades(client: TestClient, db_session_factory) -> None:
    """`DELETE /api/users/{id}` → 204, юзер и все аккаунты удалены."""
    client.post("/api/setup", json=_setup_payload())
    created = client.post("/api/users", json={"label": "Вася"}).json()

    response = client.delete(f"/api/users/{created['id']}")
    assert response.status_code == 204

    db = db_session_factory()
    try:
        assert db.scalars(select(User)).all() == []
        assert db.scalars(select(VlessAccount)).all() == []
        assert db.scalars(select(Hysteria2Account)).all() == []
        assert db.scalars(select(NaiveAccount)).all() == []
    finally:
        db.close()


def test_get_patch_delete_missing_user_returns_404(client: TestClient) -> None:
    """GET/PATCH/DELETE по несуществующему id → 404."""
    assert client.get("/api/users/999").status_code == 404
    assert client.patch("/api/users/999", json={"is_active": False}).status_code == 404
    assert client.delete("/api/users/999").status_code == 404


def test_server_config_excludes_private_key(client: TestClient) -> None:
    """`GET /api/server-config` не отдаёт `reality_private_key`."""
    client.post("/api/setup", json=_setup_payload())

    body = client.get("/api/server-config").json()
    assert "reality_private_key" not in body
    assert body["reality_public_key"] != ""