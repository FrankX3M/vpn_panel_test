"""Рендер конфигурации sing-box (контракт `03_render_singbox.md`).

Чистая функция без побочных эффектов: не читает и не пишет файлы, не выполняет
команды и не импортирует `core.svc`. Собранный ``dict`` готов к ``json.dump``
в ``/etc/sing-box/config.json`` (запись на диск — зона `07_apply_pipeline`).
"""

from __future__ import annotations

from src.core.db.models import ServerConfig, User

_VLESS_TAG = "vless-reality-in"
_HYSTERIA2_TAG = "hysteria2-in"
_VLESS_PORT = 2053
_HYSTERIA2_PORT = 443
_VLESS_FLOW = "xtls-rprx-vision"


def render_singbox_config(users: list[User], server: ServerConfig) -> dict:
    """Собрать конфиг sing-box (VLESS+Reality и Hysteria2) в виде ``dict``.

    Учитываются только пользователи с ``is_active=True`` и непустым (``is not None``)
    аккаунтом соответствующего типа. Reality ``short_id`` — список short_id всех
    активных VLESS-пользователей, чтобы можно было отозвать одного клиента,
    не перегенерируя ключи остальным.

    Аргументы:
        users: список пользователей панели.
        server: конфигурация сервера (singleton-строка ``ServerConfig``).

    Возвращает:
        ``dict``, готовый к ``json.dump`` в ``/etc/sing-box/config.json``.

    Исключения:
        ValueError: если у ``server`` пустое обязательное поле ``domain``,
            ``reality_dest`` или ``reality_private_key``, либо если
            ``reality_dest`` не является валидной парой ``host:port``.
    """
    domain = _require(server.domain, "server.domain")
    reality_private_key = _require(server.reality_private_key, "server.reality_private_key")
    dest_host, dest_port = _parse_reality_dest(server.reality_dest)

    active_users = [user for user in users if user.is_active]

    vless_users = [
        {"uuid": user.vless.uuid, "flow": _VLESS_FLOW}
        for user in active_users
        if user.vless is not None
    ]
    short_ids = [
        user.vless.short_id for user in active_users if user.vless is not None
    ]
    hysteria2_users = [
        {"name": user.label, "password": user.hysteria2.password}
        for user in active_users
        if user.hysteria2 is not None
    ]

    return {
        "log": {"level": "warn"},
        "inbounds": [
            {
                "type": "vless",
                "tag": _VLESS_TAG,
                "listen": "::",
                "listen_port": _VLESS_PORT,
                "users": vless_users,
                "tls": {
                    "enabled": True,
                    "server_name": dest_host,
                    "reality": {
                        "enabled": True,
                        "handshake": {
                            "server": dest_host,
                            "server_port": dest_port,
                        },
                        "private_key": reality_private_key,
                        "short_id": short_ids,
                    },
                },
            },
            {
                "type": "hysteria2",
                "tag": _HYSTERIA2_TAG,
                "listen": "::",
                "listen_port": _HYSTERIA2_PORT,
                "users": hysteria2_users,
                "tls": {
                    "enabled": True,
                    "acme": {
                        "domain": [domain],
                        "email": f"admin@{domain}",
                    },
                },
            },
        ],
    }


def _require(value: str, name: str) -> str:
    """Вернуть ``value``, если оно непустое, иначе бросить ``ValueError``.

    Аргументы:
        value: проверяемое значение.
        name: имя поля для текста ошибки.

    Возвращает:
        Исходное ``value``.

    Исключения:
        ValueError: если ``value`` пустое или состоит только из пробелов.
    """
    if not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _parse_reality_dest(reality_dest: str) -> tuple[str, int]:
    """Разобрать ``host:port`` на ``(host, port)``.

    Аргументы:
        reality_dest: строка вида ``"www.microsoft.com:443"``.

    Возвращает:
        Пару ``(host, port)``.

    Исключения:
        ValueError: если формат не ``host:port``, порт не целочисленный или
            выходит за пределы ``1..65535``.
    """
    host, separator, port_text = reality_dest.rpartition(":")
    if not separator or not host or not port_text:
        raise ValueError(
            f"server.reality_dest must be 'host:port', got {reality_dest!r}"
        )

    try:
        port = int(port_text)
    except ValueError:
        raise ValueError(
            f"server.reality_dest port must be an integer, got {port_text!r}"
        ) from None

    if not 1 <= port <= 65535:
        raise ValueError(f"server.reality_dest port must be in 1..65535, got {port}")

    return host, port