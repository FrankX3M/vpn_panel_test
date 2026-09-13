"""Генерация клиентских ссылок и QR-кодов (контракт `08_client_links.md`).

Чистые функции без побочных эффектов: не читают и не пишут файлы, не выполняют
команды и не обращаются к БД. Если у пользователя нет аккаунта соответствующего
типа, функция возвращает ``None``, а не бросает исключение — страница админки
просто не показывает такую ссылку.
"""

from __future__ import annotations

from urllib.parse import quote

import segno

from src.core.db.models import ServerConfig, User

_VLESS_PORT = 2053
_HYSTERIA2_PORT = 443
_NAIVE_PORT = 443
_VLESS_FLOW = "xtls-rprx-vision"


def vless_link(user: User, server: ServerConfig) -> str | None:
    """Собрать VLESS+Reality ссылку для пользователя.

    Формат:
        ``vless://<uuid>@<server.domain>:2053?security=reality&sni=<reality_dest_host>
        &fp=chrome&pbk=<reality_public_key>&sid=<short_id>&flow=xtls-rprx-vision&type=tcp#<label>``

    Аргументы:
        user: пользователь панели.
        server: конфигурация сервера (singleton-строка ``ServerConfig``).

    Возвращает:
        Готовую ссылку-строку либо ``None``, если у пользователя нет аккаунта
        ``.vless``.
    """
    if user.vless is None:
        return None

    account = user.vless
    return (
        f"vless://{quote(account.uuid)}@{quote(server.domain)}:{_VLESS_PORT}"
        f"?security=reality&sni={quote(_reality_dest_host(server.reality_dest))}"
        f"&fp=chrome&pbk={quote(server.reality_public_key)}"
        f"&sid={quote(account.short_id)}&flow={_VLESS_FLOW}&type=tcp#{quote(user.label)}"
    )


def hysteria2_link(user: User, server: ServerConfig) -> str | None:
    """Собрать Hysteria2 ссылку для пользователя.

    Формат:
        ``hysteria2://<password>@<server.domain>:443/?sni=<server.domain>#<label>``

    Аргументы:
        user: пользователь панели.
        server: конфигурация сервера (singleton-строка ``ServerConfig``).

    Возвращает:
        Готовую ссылку-строку либо ``None``, если у пользователя нет аккаунта
        ``.hysteria2``.
    """
    if user.hysteria2 is None:
        return None

    account = user.hysteria2
    return (
        f"hysteria2://{quote(account.password)}@{quote(server.domain)}:{_HYSTERIA2_PORT}/"
        f"?sni={quote(server.domain)}#{quote(user.label)}"
    )


def naive_link(user: User, server: ServerConfig) -> str | None:
    """Собрать NaiveProxy ссылку для пользователя.

    Формат:
        ``naive+https://<username>:<password>@<server.domain>:443#<label>``

    Аргументы:
        user: пользователь панели.
        server: конфигурация сервера (singleton-строка ``ServerConfig``).

    Возвращает:
        Готовую ссылку-строку либо ``None``, если у пользователя нет аккаунта
        ``.naive``.
    """
    if user.naive is None:
        return None

    account = user.naive
    return (
        f"naive+https://{quote(account.username)}:{quote(account.password)}"
        f"@{quote(server.domain)}:{_NAIVE_PORT}#{quote(user.label)}"
    )


def qr_svg(data: str) -> str:
    """Сгенерировать SVG-код QR-кода по строке ссылки.

    Используется библиотека ``segno`` (чистый Python, без ``qrcode``+Pillow).

    Аргументы:
        data: строка, которую нужно закодировать в QR.

    Возвращает:
        Строку с инлайн-SVG (начинается с тега ``<svg``).
    """
    return segno.make(data).svg_inline()


def _reality_dest_host(reality_dest: str) -> str:
    """Вернуть host-часть из строки ``host:port``.

    Аргументы:
        reality_dest: строка вида ``"www.microsoft.com:443"``.

    Возвращает:
        Часть до последнего ``:``, либо всю строку, если ``:`` отсутствует.
    """
    host, separator, _port = reality_dest.rpartition(":")
    return host if separator else reality_dest