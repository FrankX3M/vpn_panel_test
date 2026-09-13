"""Тесты для `src.core.render.links` (контракт `08_client_links.md`)."""

from __future__ import annotations

from src.core.db.models import (
    Hysteria2Account,
    NaiveAccount,
    ServerConfig,
    User,
    VlessAccount,
)
from src.core.render.links import hysteria2_link, naive_link, qr_svg, vless_link

_UUID = "11111111-1111-4111-8111-111111111111"
_SHORT_ID = "aaaaaaaa"
_CYRILLIC_LABEL = "Вася Пупкин"
_ENCODED_LABEL = "%D0%92%D0%B0%D1%81%D1%8F%20%D0%9F%D1%83%D0%BF%D0%BA%D0%B8%D0%BD"


def _user(
    *,
    vless: VlessAccount | None = None,
    hysteria2: Hysteria2Account | None = None,
    naive: NaiveAccount | None = None,
) -> User:
    """Собрать пользователя с опциональными аккаунтами без БД."""
    user = User(label=_CYRILLIC_LABEL, is_active=True)
    if vless is not None:
        user.vless = vless
    if hysteria2 is not None:
        user.hysteria2 = hysteria2
    if naive is not None:
        user.naive = naive
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
        "reality_public_key": "pub-key_123",
    }
    values.update(overrides)
    return ServerConfig(id=1, **values)


def test_vless_link_contains_uuid_sid_pbk_and_flow() -> None:
    """VLESS-ссылка начинается с `vless://` и содержит uuid/sid/pbk/flow."""
    user = _user(vless=VlessAccount(uuid=_UUID, short_id=_SHORT_ID))
    link = vless_link(user, _server())

    assert link is not None
    assert link.startswith("vless://")
    assert f"vless://{_UUID}@example.com:2053" in link
    assert "?security=reality" in link
    assert "&sni=www.microsoft.com" in link
    assert "&fp=chrome" in link
    assert "&pbk=pub-key_123" in link
    assert f"&sid={_SHORT_ID}" in link
    assert "&flow=xtls-rprx-vision&type=tcp" in link


def test_vless_link_encodes_cyrillic_label_in_fragment() -> None:
    """Кириллический `label` в `#`-фрагменте превращается в percent-encoding."""
    user = _user(vless=VlessAccount(uuid=_UUID, short_id=_SHORT_ID))
    link = vless_link(user, _server())

    assert link is not None
    assert link.endswith(f"#{_ENCODED_LABEL}")
    # исходная кириллица не попадает в ссылку необёрнутой
    assert _CYRILLIC_LABEL not in link


def test_vless_link_returns_none_without_account() -> None:
    """Пользователь без `.vless` даёт `None`, а не исключение."""
    assert vless_link(_user(), _server()) is None


def test_hysteria2_link_format() -> None:
    """Hysteria2-ссылка имеет формат hysteria2://<pass>@<domain>:443/?sni=<domain>#<label>."""
    user = _user(hysteria2=Hysteria2Account(password="hunter2"))
    link = hysteria2_link(user, _server())

    assert link is not None
    assert link.startswith("hysteria2://")
    assert "hysteria2://hunter2@example.com:443/?sni=example.com" in link
    assert link.endswith(f"#{_ENCODED_LABEL}")


def test_hysteria2_link_returns_none_without_account() -> None:
    """Пользователь без `.hysteria2` даёт `None`, а не исключение."""
    assert hysteria2_link(_user(), _server()) is None


def test_naive_link_format() -> None:
    """Naive-ссылка имеет формат naive+https://<user>:<pass>@<domain>:443#<label>."""
    user = _user(naive=NaiveAccount(username="alice", password="secret"))
    link = naive_link(user, _server())

    assert link is not None
    assert link.startswith("naive+https://")
    assert "naive+https://alice:secret@example.com:443" in link
    assert link.endswith(f"#{_ENCODED_LABEL}")


def test_naive_link_returns_none_without_account() -> None:
    """Пользователь без `.naive` даёт `None`, а не исключение."""
    assert naive_link(_user(), _server()) is None


def test_qr_svg_returns_non_empty_svg() -> None:
    """`qr_svg` любой непустой строки возвращает непустую строку, начинающуюся с `<svg`."""
    svg = qr_svg("vless://example")
    assert isinstance(svg, str)
    assert svg.strip() != ""
    assert svg.lstrip().startswith("<svg")