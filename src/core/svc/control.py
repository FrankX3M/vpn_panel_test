"""Управление системными сервисами через systemctl (контракт `05_service_control.md`)."""

import subprocess

ALLOWED_SERVICES: frozenset[str] = frozenset({"sing-box", "caddy"})
ALLOWED_ACTIONS: frozenset[str] = frozenset({"restart", "reload", "status"})


class ServiceControlError(Exception):
    """Ошибка управления сервисом: service или action вне whitelist."""


def control(service: str, action: str) -> subprocess.CompletedProcess:
    """Выполнить ``sudo systemctl <action> <service>``.

    Аргументы:
        service: имя сервиса; должно входить в ``ALLOWED_SERVICES``.
        action: действие; должно входить в ``ALLOWED_ACTIONS``.

    Возвращает:
        ``subprocess.CompletedProcess`` с результатом выполнения команды.

    Исключения:
        ServiceControlError: если ``service`` или ``action`` не входит в whitelist.
            Проверка выполняется до сборки команды.
        subprocess.TimeoutExpired: если команда не завершилась за ``timeout``.
    """
    if service not in ALLOWED_SERVICES:
        raise ServiceControlError(f"service not allowed: {service!r}")
    if action not in ALLOWED_ACTIONS:
        raise ServiceControlError(f"action not allowed: {action!r}")

    return subprocess.run(
        ["sudo", "systemctl", action, service],
        capture_output=True,
        timeout=10,
    )