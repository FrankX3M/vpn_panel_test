"""E2E "создать пользователя → конфиги валидны → отключить" (ТЗ `integration_01_e2e.md`).

Единственный сквозной сценарий через ``TestClient`` без моков ``render_*`` и
``core.db``. Подменяется только ``core.svc.control.control`` (реальный
``systemctl`` в тестовой среде может отсутствовать), а боевые пути конфигов
переводятся на ``tmp_path`` — реальный ``/etc`` не затрагивается.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.users import get_db
from src.core import config
from src.core.db.models import Base
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
    """``CompletedProcess`` с нулевым returncode (успешный reload)."""
    return subprocess.CompletedProcess(
        args=["sudo", "systemctl", "reload", "service"],
        returncode=0,
        stdout=b"",
        stderr=b"",
    )


@pytest.fixture
def control_calls(monkeypatch) -> list[tuple[str, str]]:
    """Мок ``core.svc.control.control``: записывает вызовы и возвращает успех."""
    calls: list[tuple[str, str]] = []

    def fake_control(service: str, action: str) -> subprocess.CompletedProcess:
        calls.append((service, action))
        return _successful_control()

    monkeypatch.setattr("src.core.svc.control.control", fake_control)
    return calls


@pytest.fixture
def client(
    db_session_factory, paths, control_calls
) -> Generator[TestClient, None, None]:
    """``TestClient`` с тестовой БД; ``render_*`` и ``core.db`` не мокаются."""

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
    """Валидное тело для ``POST /api/setup``."""
    return {
        "domain": "example.com",
        "admin_domain": "panel.example.com",
        "admin_username": "admin",
        "admin_password_hash": "$2b$12$hash",
        "reality_dest": "www.microsoft.com:443",
    }


def _vless_uuids(singbox_path: Path) -> set[str]:
    """Вернуть множество uuid активных VLESS-пользователей из sing-box JSON."""
    singbox = json.loads(singbox_path.read_text(encoding="utf-8"))
    for inbound in singbox["inbounds"]:
        if inbound["tag"] == "vless-reality-in":
            return {user["uuid"] for user in inbound["users"]}
    return set()


def test_e2e_create_user_apply_disable_removes_credentials(
    client: TestClient,
    paths,
    control_calls: list[tuple[str, str]],
) -> None:
    """Создание кладёт uuid/username в конфиги, отключение — убирает их оттуда.

    ``control`` вызывается для sing-box и caddy на каждом из двух ``apply``:
    при создании пользователя и при ``PATCH is_active=false``.
    """
    client.post("/api/setup", json=_setup_payload())

    created = client.post("/api/users", json={"label": "Тест Юзер"})
    assert created.status_code == 201
    body = created.json()
    vless_uuid = body["vless"]["uuid"]
    naive_username = body["naive"]["username"]

    # После создания учётные данные реально присутствуют в сгенерированных файлах.
    assert vless_uuid in _vless_uuids(paths["singbox"])
    caddy_after_create = paths["caddy"].read_text(encoding="utf-8")
    assert naive_username in caddy_after_create

    # Первый apply (при создании) перезагрузил оба сервиса.
    assert control_calls == [("sing-box", "reload"), ("caddy", "reload")]

    control_calls.clear()

    patched = client.patch(f"/api/users/{body['id']}", json={"is_active": False})
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    # После отключения учётные данные исчезли из файлов конфигов,
    # а не только флаг в БД сменился.
    assert vless_uuid not in _vless_uuids(paths["singbox"])
    caddy_after_disable = paths["caddy"].read_text(encoding="utf-8")
    assert naive_username not in caddy_after_disable

    # Второй apply (при PATCH) снова перезагрузил оба сервиса.
    assert control_calls == [("sing-box", "reload"), ("caddy", "reload")]