"""Тесты для `src.core.keys.generate` (контракт `02_key_generation.md`)."""

from __future__ import annotations

import base64
import re
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from src.core.keys.generate import (
    new_naive_username,
    new_password,
    new_reality_keypair,
    new_reality_short_id,
    new_vless_uuid,
)

_SHORT_ID_RE = re.compile(r"^[0-9a-f]{8}$")
_NAIVE_RE = re.compile(r"^[a-z0-9_]{3,32}$")
_URLSAFE_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _b64url_decode(value: str) -> bytes:
    """Декодировать base64url без padding, восстановив '=' для urlsafe_b64decode."""
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def test_vless_uuid_is_version_4() -> None:
    """`new_vless_uuid()` возвращает валидный UUID v4."""
    value = new_vless_uuid()
    assert uuid.UUID(value, version=4)


def test_vless_uuid_values_differ() -> None:
    """Два вызова `new_vless_uuid()` дают разные значения."""
    assert new_vless_uuid() != new_vless_uuid()


def test_reality_short_id_matches_pattern() -> None:
    """`new_reality_short_id()` — ровно 8 hex-символов `[0-9a-f]{8}`."""
    assert _SHORT_ID_RE.fullmatch(new_reality_short_id())


def test_reality_short_id_values_differ() -> None:
    """Два вызова `new_reality_short_id()` дают разные значения."""
    assert new_reality_short_id() != new_reality_short_id()


def test_reality_keypair_format() -> None:
    """Ключи — непустые base64url-строки без padding, декодируются в 32 байта."""
    private, public = new_reality_keypair()

    assert private and public and private != public
    assert "=" not in private and "=" not in public
    assert len(_b64url_decode(private)) == 32
    assert len(_b64url_decode(public)) == 32


def test_reality_keypair_private_matches_public() -> None:
    """Публичный ключ восстанавливается из приватного (X25519)."""
    private, public = new_reality_keypair()

    private_key = X25519PrivateKey.from_private_bytes(_b64url_decode(private))
    derived_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    assert derived_public == _b64url_decode(public)


def test_reality_keypair_values_differ() -> None:
    """Два вызова `new_reality_keypair()` дают разные приватные ключи."""
    first_private, _ = new_reality_keypair()
    second_private, _ = new_reality_keypair()
    assert first_private != second_private


def test_new_password_default_length() -> None:
    """`new_password()` по умолчанию — URL-safe строка, кодирующая 24 байта -> 32 символа."""
    value = new_password()
    assert len(value) == 32
    assert _URLSAFE_RE.fullmatch(value)
    assert "=" not in value


def test_new_password_custom_length_uses_nbytes() -> None:
    """Параметр `length` трактуется как байты энтропии (nbytes), а не длина строки."""
    assert len(new_password(3)) == 4  # 3 байта -> 4 base64-символа без padding
    assert "=" not in new_password(1)


def test_new_password_values_differ() -> None:
    """Два вызова `new_password()` дают разные значения."""
    assert new_password() != new_password()


def test_naive_username_transliterates_cyrillic() -> None:
    """`new_naive_username('Вася')` транслитерируется в 'vasya'."""
    assert new_naive_username("Вася") == "vasya"


def test_naive_username_collision_adds_suffix() -> None:
    """При коллизии с existing={'vasya'} возвращается 'vasya-2'."""
    assert new_naive_username("Вася", {"vasya"}) == "vasya-2"


def test_naive_username_collision_two_collisions() -> None:
    """При занятых 'vasya' и 'vasya-2' возвращается 'vasya-3'."""
    assert new_naive_username("Вася", {"vasya", "vasya-2"}) == "vasya-3"


def test_naive_username_empty_string_is_valid() -> None:
    """Пустая строка не падает и даёт валидное `[a-z0-9_]{3,32}`."""
    value = new_naive_username("")
    assert _NAIVE_RE.fullmatch(value)


def test_naive_username_digits_only_is_valid() -> None:
    """Только цифры не падает и даёт валидный результат."""
    value = new_naive_username("123")
    assert _NAIVE_RE.fullmatch(value)


def test_naive_username_special_chars_only_is_valid() -> None:
    """Только спецсимволы не падает и даёт валидный результат."""
    value = new_naive_username("!@#$%^&*")
    assert _NAIVE_RE.fullmatch(value)


def test_naive_username_long_label_truncated() -> None:
    """Длинная подпись обрезается до 32 символов."""
    value = new_naive_username("а" * 100)
    assert _NAIVE_RE.fullmatch(value)
    assert len(value) == 32


def test_naive_username_keeps_latin_and_digits() -> None:
    """Латиница и цифры сохраняются, без неожиданной транслитерации."""
    value = new_naive_username("admin123")
    assert value == "admin123"