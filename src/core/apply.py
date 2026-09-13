"""Применение конфигов: рендер → temp-файл → os.replace → reload (контракт `07_apply_pipeline.md`).

Запись всегда идёт через временный файл и ``os.replace``, чтобы ``systemctl
reload`` не подхватил наполовину записанный конфиг. Ошибки применения поднимают
``ApplyError`` без автоматического отката файлов — откат выполняет администратор.
"""

from __future__ import annotations

import json
import os
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core import config
from src.core.db.models import ServerConfig, User
from src.core.render.caddy import render_caddyfile
from src.core.render.singbox import render_singbox_config
from src.core.svc import control as service_control


class ApplyError(Exception):
    """Ошибка применения конфигов (запись файла или reload сервиса)."""


def apply(session: Session) -> None:
    """Собрать и применить актуальные конфиги sing-box и Caddy.

    Аргументы:
        session: SQLAlchemy-сессия, из которой читаются пользователи и
            ``ServerConfig``.

    Исключения:
        ApplyError: если ``ServerConfig`` отсутствует, не удалось записать файл
            или reload одного из сервисов завершился с ненулевым кодом/исключением.
    """
    users = list(session.scalars(select(User)).all())
    server = session.get(ServerConfig, 1)
    if server is None:
        raise ApplyError("ServerConfig not found")

    singbox_config = render_singbox_config(users, server)
    caddyfile = render_caddyfile(users, server)

    _write_atomic(config.SINGBOX_CONFIG_PATH, json.dumps(singbox_config, indent=2))
    _write_atomic(config.CADDYFILE_PATH, caddyfile)

    _reload("sing-box")
    _reload("caddy")


def _write_atomic(path: str, content: str) -> None:
    """Записать ``content`` в ``path`` атомарно (temp-файл + ``os.replace``).

    Аргументы:
        path: целевой путь к файлу.
        content: текстовое содержимое.

    Исключения:
        ApplyError: если запись или замена файла не удалась.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except OSError as exc:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise ApplyError(f"failed to write {path}: {exc}") from exc


def _reload(service: str) -> None:
    """Перечитать конфиг сервиса через ``core.svc.control``.

    Аргументы:
        service: имя сервиса (``sing-box`` или ``caddy``).

    Исключения:
        ApplyError: если ``control`` бросил исключение или вернул ненулевой
            ``returncode``. Текст ошибки включает stderr от systemctl.
    """
    try:
        result = service_control.control(service, "reload")
    except Exception as exc:  # noqa: BLE001 — обёртка ошибки в ApplyError
        raise ApplyError(f"{service} reload failed: {exc}") from exc

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ApplyError(f"{service} reload failed: {stderr}")