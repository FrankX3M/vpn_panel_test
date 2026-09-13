"""Тесты для `src.core.svc.control` (контракт `05_service_control.md`)."""

from unittest.mock import patch

import pytest

from src.core.svc.control import (
    ALLOWED_ACTIONS,
    ALLOWED_SERVICES,
    ServiceControlError,
    control,
)


def test_control_reload_sing_box_calls_run_with_list_args() -> None:
    """`control("sing-box", "reload")` передаёт команду списком, не строкой."""
    with patch("src.core.svc.control.subprocess.run") as mock_run:
        control("sing-box", "reload")

    mock_run.assert_called_once_with(
        ["sudo", "systemctl", "reload", "sing-box"],
        capture_output=True,
        timeout=10,
    )


def test_control_service_not_in_whitelist() -> None:
    """Сервис не из whitelist -> ServiceControlError, без вызова subprocess.run."""
    with patch("src.core.svc.control.subprocess.run") as mock_run:
        with pytest.raises(ServiceControlError):
            control("nginx", "restart")

    mock_run.assert_not_called()


def test_control_action_not_in_whitelist() -> None:
    """Действие не из whitelist -> ServiceControlError, без вызова subprocess.run."""
    with patch("src.core.svc.control.subprocess.run") as mock_run:
        with pytest.raises(ServiceControlError):
            control("caddy", "stop")

    mock_run.assert_not_called()


def test_control_passes_timeout() -> None:
    """Функция передаёт timeout в subprocess.run (не бесконечное ожидание)."""
    with patch("src.core.svc.control.subprocess.run") as mock_run:
        control("caddy", "status")

    kwargs = mock_run.call_args.kwargs
    assert kwargs["timeout"] == 10


def test_whitelists_contain_expected_values() -> None:
    """Контрактные whitelist-значения не расширены/не урезаны без нужды."""
    assert ALLOWED_SERVICES == frozenset({"sing-box", "caddy"})
    assert ALLOWED_ACTIONS == frozenset({"restart", "reload", "status"})