"""
Регрессионный тест: приложение должно создавать все таблицы БД при реальном старте
(через lifespan FastAPI, запущенный в отдельном процессе с чистым рабочим каталогом),
а не только когда init_db() вызван вручную в фикстуре теста.

Баг, который это ловит: src/main.py не вызывал core.db.session.init_db() при старте
(engine в session.py указывает на sqlite:///./vpn_panel.db — путь относительно cwd,
поэтому тест запускает приложение в отдельном subprocess с cwd=tmp_path, чтобы не
трогать ни боевую БД, ни файлы других тестов, и не зависеть от кэша sys.modules
внутри одного процесса pytest).
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_CHILD_SCRIPT = textwrap.dedent(
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, inspect

    from src.main import app

    with TestClient(app):
        pass  # вход/выход из контекста прогоняет lifespan (startup/shutdown)

    engine = create_engine("sqlite:///./vpn_panel.db")
    tables = set(inspect(engine).get_table_names())
    expected = {"users", "vless_accounts", "hysteria2_accounts", "naive_accounts", "server_config"}
    missing = expected - tables
    if missing:
        raise SystemExit(f"MISSING_TABLES:{missing}")
    print("OK")
    """
)


def test_app_startup_creates_all_tables(tmp_path):
    """Реальный старт приложения (как в проде — cwd = корень репо, см. systemd
    WorkingDirectory) → все таблицы созданы. Побочный vpn_panel.db, который
    создаст init_db() в REPO_ROOT, временно отводится в сторону и убирается
    после теста, чтобы не задеть боевой файл, если он есть локально."""
    script_path = tmp_path / "_check_startup.py"
    script_path.write_text(_CHILD_SCRIPT, encoding="utf-8")

    db_path = REPO_ROOT / "vpn_panel.db"
    backup_path = tmp_path / "vpn_panel.db.bak"
    had_existing_db = db_path.exists()
    if had_existing_db:
        db_path.rename(backup_path)

    try:
        child_env = dict(os.environ)
        child_env["PYTHONPATH"] = str(REPO_ROOT)
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=REPO_ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
    finally:
        db_path.unlink(missing_ok=True)
        if had_existing_db:
            backup_path.rename(db_path)

    assert result.returncode == 0, (
        f"Приложение не создало все таблицы при старте.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}\n"
        f"Проверь, что src/main.py вызывает core.db.session.init_db() в lifespan."
    )
    assert "OK" in result.stdout
