"""Генерация ключей для VPN-панели (контракт `02_key_generation.md`).

Все функции здесь — чистые в смысле отсутствия побочных эффектов: не пишут в БД,
не читают файлы, не логируют. Детерминированность входа/выхода не предполагается
(используются ``secrets``/``os.urandom``/``uuid.uuid4``/X25519).
"""

from __future__ import annotations

import base64
import os
import secrets
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

# Транслитерация только строчных букв: входной label приводится к нижнему регистру
# до транслитерации, поэтому таблица содержит только нижний регистр.
_TRANSLIT: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "yo",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def new_vless_uuid() -> str:
    """Сгенерировать UUID v4.

    Возвращает:
        UUID версии 4 в канонической строковой форме (``str(uuid.uuid4())``).
    """
    return str(uuid.uuid4())


def new_reality_short_id() -> str:
    """Сгенерировать Reality short_id: 8 шестнадцатеричных символов.

    Возвращает:
        Строка вида ``[0-9a-f]{8}`` (``os.urandom(4).hex()``).
    """
    return os.urandom(4).hex()


def new_reality_keypair() -> tuple[str, str]:
    """Сгенерировать X25519-пару ключей Reality для sing-box.

    Реализация: ``cryptography.hazmat.primitives.asymmetric.x25519`` — ключи
    генерируются библиотекой ``cryptography`` (``X25519PrivateKey.generate()``),
    без вызова бинарника sing-box и без парсинга его stdout, поэтому функция
    работает и на машинах, где sing-box не установлен.

    Возвращает:
        ``(private_key, public_key)`` — X25519-ключи в формате base64url
        без padding (``=``), который ожидает sing-box в полях
        ``private_key``/``public_key``.
    """
    private = X25519PrivateKey.generate()
    private_bytes = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64url_nopad(private_bytes), _b64url_nopad(public_bytes)


def new_password(length: int = 24) -> str:
    """Сгенерировать URL-safe пароль.

    Параметр ``length`` — это **количество байт энтропии** (``nbytes``),
    передаваемое в ``secrets.token_urlsafe``, а не итоговая длина строки.
    Итоговая длина строки — ``ceil(4/3 * length)`` символов без padding
    ``=`` (для ``length=24`` — ровно 32 символа).

    Аргументы:
        length: количество байт энтропии.

    Возвращает:
        URL-safe строка из ``secrets.token_urlsafe(length)``.
    """
    return secrets.token_urlsafe(length)


def new_naive_username(label: str, existing: set[str] | None = None) -> str:
    """Построить NaiveProxy-имя пользователя из произвольной подписи.

    Транслитерирует ``label`` (кириллица → латиница), приводит к нижнему
    регистру, заменяет все символы вне ``[a-z0-9_]`` на ``_``, затем
    приводит длину к диапазону ``[3, 32]``. Короткие результаты дополняются
    ``_`` справа до минимальной длины 3, длинные — обрезаются до 32.
    Если результат уже присутствует в ``existing``, к базе добавляется суффикс
    ``-2``, ``-3``, ... через ``-`` до первого свободного имени.

    Аргументы:
        label: исходная подпись; может содержать кириллицу, цифры, спецсимволы
            и может быть пустой.
        existing: множество уже занятых имён для проверки коллизий.

    Возвращает:
        Уникальное имя в формате ``[a-z0-9_]{3,32}`` (при коллизии — с суффиксом
        ``-N``).
    """
    if existing is None:
        existing = set()

    transliterated = "".join(_TRANSLIT.get(ch, ch) for ch in label.lower())
    base = "".join(
        ch if ("a" <= ch <= "z" or "0" <= ch <= "9" or ch == "_") else "_"
        for ch in transliterated
    )

    if len(base) < 3:
        base = base.ljust(3, "_")
    elif len(base) > 32:
        base = base[:32]

    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _b64url_nopad(data: bytes) -> str:
    """Закодировать байты в base64url без padding, вернуть ASCII-строку."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")