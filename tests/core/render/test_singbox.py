"""Тесты для `src.core.render.singbox` (контракт `03_render_singbox.md`)."""

from __future__ import annotations

import json

import pytest

from src.core.db.models import Hysteria2Account, ServerConfig, User, VlessAccount
from src.core.render.singbox import render_singbox_config

_UUID_A = "11111111-1111-4111-8111-111111111111"
_UUID_B = "22222222-2222-4222-8222-222222222222"
_UUID_INACTIVE = "33333333-3333-4333-8333-333333333333"
_SHORT_A = "aaaaaaaa"
_SHORT_B = "bbbbbbbb"


def _vless(uuid: str = _UUID_A, short_id: str = _SHORT_A) -> VlessAccount:
    """Создать VLESS-аккаунт с заданными uuid/short_id."""
    return VlessAccount(uuid=uuid, short_id=short_id)


def _hy2(password: str = "hy2-password") -> Hysteria2Account:
    """Создать Hysteria2-аккаунт с заданным паролем."""
    return Hysteria2Account(password=password)


def _user(
    label: str = "user",
    *,
    is_active: bool = True,
    vless: VlessAccount | None = None,
    hysteria2: Hysteria2Account | None = None,
) -> User:
    """Собрать пользователя с опциональными аккаунтами без БД."""
    user = User(label=label, is_active=is_active)
    if vless is not None:
        user.vless = vless
    if hysteria2 is not None:
        user.hysteria2 = hysteria2
    return user


def _server(**overrides: str) -> ServerConfig:
    """Собрать валидный ServerConfig, перекрывая отдельные поля."""
    values: dict[str, str] = {
        "domain": "example.com",
        "admin_domain": "panel.example.com",
        "admin_username": "admin",
        "admin_password_hash": "$2b$12$hash",
        "reality_dest": "www.microsoft.com:443",
        "reality_private_key": "private-key",
        "reality_public_key": "public-key",
    }
    values.update(overrides)
    return ServerConfig(id=1, **values)


def _inbounds(config: dict) -> dict[str, dict]:
    """Вернуть inbound'ы по tag для удобных проверок."""
    return {item["tag"]: item for item in config["inbounds"]}


def test_config_is_json_serializable() -> None:
    """Результат сериализуется через `json.dumps` без ошибок."""
    config = render_singbox_config(
        [_user("a", vless=_vless(), hysteria2=_hy2())], _server()
    )
    serialized = json.dumps(config)
    assert isinstance(serialized, str)


def test_active_vless_users_and_short_ids_exclude_inactive() -> None:
    """VLESS uuid/short_id учитывают только активных пользователей с `.vless`."""
    only_vless = _user("only-vless", vless=_vless(uuid=_UUID_A, short_id=_SHORT_A))
    both = _user(
        "both",
        vless=_vless(uuid=_UUID_B, short_id=_SHORT_B),
        hysteria2=_hy2(password="hy2-secret"),
    )
    inactive = _user(
        "inactive", is_active=False, vless=_vless(uuid=_UUID_INACTIVE, short_id="cccccccc")
    )

    config = render_singbox_config([only_vless, both, inactive], _server())
    vless_inbound = _inbounds(config)["vless-reality-in"]

    vless_uuids = {item["uuid"] for item in vless_inbound["users"]}
    assert vless_uuids == {_UUID_A, _UUID_B}
    assert _UUID_INACTIVE not in vless_uuids

    short_ids = vless_inbound["tls"]["reality"]["short_id"]
    assert set(short_ids) == {_SHORT_A, _SHORT_B}


def test_hysteria2_filters_inactive_and_accountless() -> None:
    """Hysteria2 users учитывает только активных пользователей с `.hysteria2`."""
    accountless = _user("no-hy2", vless=_vless())
    inactive = _user("hy2-inactive", is_active=False, hysteria2=_hy2(password="gone"))
    active = _user("hy2-active", hysteria2=_hy2(password="alive"))

    config = render_singbox_config([accountless, inactive, active], _server())
    assert _inbounds(config)["hysteria2-in"]["users"] == [
        {"name": "hy2-active", "password": "alive"},
    ]


def test_empty_users_produces_valid_structure() -> None:
    """Пустой список пользователей не падает и даёт пустые users/short_id."""
    config = render_singbox_config([], _server())
    inbounds = _inbounds(config)

    assert inbounds["vless-reality-in"]["users"] == []
    assert inbounds["vless-reality-in"]["tls"]["reality"]["short_id"] == []
    assert inbounds["hysteria2-in"]["users"] == []


def test_static_inbound_fields() -> None:
    """Константные поля inbound'ов (tag/listen/port/tls/acme) совпадают с контрактом."""
    config = render_singbox_config([], _server())
    inbounds = _inbounds(config)

    vless = inbounds["vless-reality-in"]
    assert vless["type"] == "vless"
    assert vless["listen"] == "::"
    assert vless["listen_port"] == 2053
    assert vless["tls"]["enabled"] is True
    assert vless["tls"]["reality"]["enabled"] is True

    hy2 = inbounds["hysteria2-in"]
    assert hy2["type"] == "hysteria2"
    assert hy2["listen"] == "::"
    assert hy2["listen_port"] == 443
    assert hy2["tls"]["enabled"] is True
    assert hy2["tls"]["acme"]["domain"] == ["example.com"]
    assert hy2["tls"]["acme"]["email"] == "admin@example.com"


def test_vless_users_have_flow() -> None:
    """Каждый VLESS-пользователь получает flow `xtls-rprx-vision`."""
    config = render_singbox_config([_user("a", vless=_vless(uuid=_UUID_A))], _server())
    assert _inbounds(config)["vless-reality-in"]["users"] == [
        {"uuid": _UUID_A, "flow": "xtls-rprx-vision"},
    ]


def test_reality_dest_parsed_into_host_port_and_handshake() -> None:
    """`reality_dest` разбирается на host/port для server_name и handshake."""
    config = render_singbox_config([], _server(reality_dest="example.org:8443"))
    tls = _inbounds(config)["vless-reality-in"]["tls"]

    assert tls["server_name"] == "example.org"
    assert tls["reality"]["handshake"] == {"server": "example.org", "server_port": 8443}
    assert tls["reality"]["private_key"] == "private-key"


@pytest.mark.parametrize("field", ["domain", "reality_dest", "reality_private_key"])
def test_missing_required_server_fields_raise_value_error(field: str) -> None:
    """Пустое обязательное поле server даёт ValueError, а не KeyError/AttributeError."""
    with pytest.raises(ValueError):
        render_singbox_config([], _server(**{field: ""}))


@pytest.mark.parametrize(
    "bad",
    ["example.org", "example.org:", ":443", "example.org:notaport", "example.org:0"],
)
def test_invalid_reality_dest_raises_value_error(bad: str) -> None:
    """Некорректный `reality_dest` даёт ValueError с понятным текстом."""
    with pytest.raises(ValueError):
        render_singbox_config([], _server(reality_dest=bad))