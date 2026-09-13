"""Тесты для `src.core.apply` (контракт `07_apply_pipeline.md`).

Запись идёт в ``tmp_path`` (через monkeypatch констант путей в
``src.core.config``) и не трогает реальный ``/etc``. Вызов ``systemctl``
подменяется моком ``src.core.svc.control.control``.
"""

from __future__ import annotations

import json
import subprocess

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core import config
from src.core.apply import ApplyError, apply
from src.core.db.models import (
    Base,
    Hysteria2Account,
    NaiveAccount,
    ServerConfig,
    User,
    VlessAccount,
)


@pytest.fixture
def db_session_factory():
    """In-memory SQLite с общей схемой в рамках одного соединения."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def _server() -> ServerConfig:
    """Валидный singleton-``ServerConfig``."""
    return ServerConfig(
        id=1,
        domain="example.com",
        admin_domain="panel.example.com",
        admin_username="admin",
        admin_password_hash="$2b$12$hash",
        reality_dest="www.microsoft.com:443",
        reality_private_key="private-key",
        reality_public_key="public-key",
    )


def _active_user(label: str = "user1") -> User:
    """Активный пользователь со всеми тремя аккаунтами."""
    user = User(label=label, is_active=True)
    user.vless = VlessAccount(
        uuid="11111111-1111-4111-8111-111111111111", short_id="aaaaaaaa"
    )
    user.hysteria2 = Hysteria2Account(password="hysteria2-password")
    user.naive = NaiveAccount(username="user1", password="naive-password")
    return user


def _seed(session: Session) -> None:
    """Создать сервер и пользователя в сессии."""
    session.add(_server())
    session.add(_active_user())
    session.commit()


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Подменить боевые пути на ``tmp_path`` и вернуть их для проверок."""
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


def test_apply_writes_valid_json_and_caddyfile(
    db_session_factory, paths, monkeypatch
) -> None:
    """После apply файлы записаны: JSON валиден и соответствует БД, Caddyfile непустой."""
    calls: list[tuple[str, str]] = []

    def fake_control(service: str, action: str) -> subprocess.CompletedProcess:
        calls.append((service, action))
        return _successful_control()

    monkeypatch.setattr("src.core.svc.control.control", fake_control)

    db = db_session_factory()
    try:
        _seed(db)
        apply(db)
    finally:
        db.close()

    singbox = json.loads(paths["singbox"].read_text(encoding="utf-8"))
    inbounds = {item["tag"]: item for item in singbox["inbounds"]}
    vless_users = inbounds["vless-reality-in"]["users"]
    assert len(vless_users) == 1
    assert vless_users[0]["uuid"] == "11111111-1111-4111-8111-111111111111"

    caddy = paths["caddy"].read_text(encoding="utf-8")
    assert caddy.strip() != ""


def test_apply_reloads_both_services_once(db_session_factory, paths, monkeypatch) -> None:
    """control вызывается ровно по разу для sing-box и caddy с действием reload."""
    calls: list[tuple[str, str]] = []

    def fake_control(service: str, action: str) -> subprocess.CompletedProcess:
        calls.append((service, action))
        return _successful_control()

    monkeypatch.setattr("src.core.svc.control.control", fake_control)

    db = db_session_factory()
    try:
        _seed(db)
        apply(db)
    finally:
        db.close()

    assert calls == [("sing-box", "reload"), ("caddy", "reload")]


def test_apply_leaves_no_tmp_files(db_session_factory, paths, monkeypatch) -> None:
    """После успешного apply не остаётся ``.tmp``-файлов в каталоге записи."""
    monkeypatch.setattr(
        "src.core.svc.control.control",
        lambda service, action: _successful_control(),
    )

    db = db_session_factory()
    try:
        _seed(db)
        apply(db)
    finally:
        db.close()

    leftovers = [
        path
        for path in paths["singbox"].parent.iterdir()
        if path.name.startswith(".tmp-")
    ]
    assert leftovers == []


def test_apply_raises_apply_error_on_nonzero_returncode_and_keeps_files(
    db_session_factory, paths, monkeypatch
) -> None:
    """Ненулевой returncode caddy → ApplyError со stderr, файлы уже записаны."""
    monkeypatch.setattr(
        "src.core.svc.control.control",
        lambda service, action: subprocess.CompletedProcess(
            args=["sudo", "systemctl", action, service],
            returncode=1,
            stdout=b"",
            stderr=b"invalid Caddyfile",
        ),
    )

    db = db_session_factory()
    try:
        _seed(db)
        with pytest.raises(ApplyError) as exc_info:
            apply(db)
    finally:
        db.close()

    assert "invalid Caddyfile" in str(exc_info.value)
    assert paths["singbox"].exists()
    assert paths["caddy"].exists()


def test_apply_raises_apply_error_when_control_raises_and_keeps_files(
    db_session_factory, paths, monkeypatch
) -> None:
    """Исключение из control для caddy → ApplyError, файлы уже записаны (без отката)."""
    calls: list[tuple[str, str]] = []

    def fake_control(service: str, action: str) -> subprocess.CompletedProcess:
        calls.append((service, action))
        if service == "caddy":
            raise RuntimeError("systemctl crashed")
        return _successful_control()

    monkeypatch.setattr("src.core.svc.control.control", fake_control)

    db = db_session_factory()
    try:
        _seed(db)
        with pytest.raises(ApplyError) as exc_info:
            apply(db)
    finally:
        db.close()

    assert "caddy reload failed" in str(exc_info.value)
    assert "systemctl crashed" in str(exc_info.value)
    assert calls == [("sing-box", "reload"), ("caddy", "reload")]
    assert paths["singbox"].exists()
    assert paths["caddy"].exists()


def test_apply_raises_apply_error_when_server_config_missing(
    db_session_factory, paths, monkeypatch
) -> None:
    """Без ServerConfig apply поднимает ApplyError и не трогает сервисы."""
    monkeypatch.setattr(
        "src.core.svc.control.control",
        lambda service, action: _successful_control(),
    )

    db = db_session_factory()
    try:
        with pytest.raises(ApplyError):
            apply(db)
    finally:
        db.close()

    assert not paths["singbox"].exists()
    assert not paths["caddy"].exists()