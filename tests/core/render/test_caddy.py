"""Тесты для `src.core.render.caddy` (контракт `04_render_caddy.md`)."""

from __future__ import annotations

from src.core.db.models import NaiveAccount, ServerConfig, User
from src.core.render.caddy import render_caddyfile


def _naive(username: str = "user1", password: str = "pass1") -> NaiveAccount:
    """Создать Naive-аккаунт с заданными username/password."""
    return NaiveAccount(username=username, password=password)


def _user(
    label: str = "user",
    *,
    is_active: bool = True,
    naive: NaiveAccount | None = None,
) -> User:
    """Собрать пользователя с опциональным Naive-аккаунтом без БД."""
    user = User(label=label, is_active=is_active)
    if naive is not None:
        user.naive = naive
    return user


def _server(**overrides: str) -> ServerConfig:
    """Собрать валидный ServerConfig, перекрывая отдельные поля."""
    values: dict[str, str] = {
        "domain": "example.com",
        "admin_domain": "panel.example.com",
        "admin_username": "admin",
        "admin_password_hash": "$2b$12$abcdefgh",
        "reality_dest": "www.microsoft.com:443",
        "reality_private_key": "private-key",
        "reality_public_key": "public-key",
    }
    values.update(overrides)
    return ServerConfig(id=1, **values)


def test_contains_global_options_block() -> None:
    """Глобальный блок содержит order forward_proxy перед reverse_proxy."""
    result = render_caddyfile([], _server())
    assert "order forward_proxy before reverse_proxy" in result
    assert result.startswith("{\n")


def test_domain_block_with_forward_proxy_and_not_found() -> None:
    """Site-блок naive содержит forward_proxy и respond 'Not Found' 404."""
    result = render_caddyfile([], _server())
    assert "example.com {" in result
    assert "\tforward_proxy {" in result
    assert '\trespond "Not Found" 404' in result


def test_forward_proxy_always_has_masking_directives() -> None:
    """Даже без аккаунтов forward_proxy содержит hide_ip/hide_via/probe_resistance."""
    result = render_caddyfile([], _server())
    assert "\t\thide_ip" in result
    assert "\t\thide_via" in result
    assert "\t\tprobe_resistance" in result


def test_active_naive_users_get_basic_auth_lines() -> None:
    """Каждый активный Naive-аккаунт даёт строку basic_auth username password."""
    users = [
        _user("a", naive=_naive("alice", "secret-a")),
        _user("b", naive=_naive("bob", "secret-b")),
    ]
    result = render_caddyfile(users, _server())
    assert "\t\tbasic_auth alice secret-a" in result
    assert "\t\tbasic_auth bob secret-b" in result


def test_inactive_and_accountless_users_are_skipped() -> None:
    """Неактивные и пользователи без .naive не попадают в basic_auth."""
    users = [
        _user("active", naive=_naive("alice", "secret-a")),
        _user("inactive", is_active=False, naive=_naive("mallory", "secret-m")),
        _user("no-naive"),
    ]
    result = render_caddyfile(users, _server())
    assert "basic_auth alice secret-a" in result
    assert "basic_auth mallory" not in result
    assert "basic_auth no-naive" not in result


def test_admin_block_always_one_with_basicauth_and_reverse_proxy() -> None:
    """Блок админки всегда один с basicauth и reverse_proxy на localhost:8000."""
    result = render_caddyfile([], _server())
    assert result.count("panel.example.com {") == 1
    assert "\tbasicauth {" in result
    assert "\t\tadmin $2b$12$abcdefgh" in result
    assert "\treverse_proxy 127.0.0.1:8000" in result


def test_empty_naive_accounts_keeps_valid_syntax() -> None:
    """Пустой список аккаунтов не даёт empty basic_auth, блок остаётся валидным."""
    result = render_caddyfile([], _server())
    forward_proxy_block = result[result.index("\tforward_proxy {") : result.index("\t}")]
    # внутри forward_proxy нет пустых строк basic_auth
    assert "basic_auth" not in forward_proxy_block


def test_balanced_braces() -> None:
    """Количество открывающих и закрывающих фигурных скобок совпадает."""
    result = render_caddyfile(
        [_user("a", naive=_naive("alice", "secret-a"))], _server()
    )
    assert result.count("{") == result.count("}")