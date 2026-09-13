"""Рендер Caddyfile (контракт `04_render_caddy.md`).

Чистая функция без побочных эффектов: не читает и не пишет файлы и не
выполняет команды. Результат готов к записи в ``/etc/caddy/Caddyfile``
(запись на диск — зона `07_apply_pipeline`).
"""

from __future__ import annotations

from src.core.db.models import ServerConfig, User


def render_caddyfile(users: list[User], server: ServerConfig) -> str:
    """Вернуть содержимое Caddyfile целиком (naive-прокси и админка).

    Рендер состоит из глобального блока опций (директива ``order`` для модуля
    ``forwardproxy``), site-блока naive-прокси на ``server.domain`` и
    site-блока админки на ``server.admin_domain``.

    Учитываются только пользователи с ``is_active=True`` и непустым
    ``.naive``: каждый такой аккаунт даёт отдельную строку
    ``basic_auth <username> <password>`` внутри ``forward_proxy``.

    Инъекция в конфиг через учётные данные исключена за счёт безопасного
    алфавита, гарантированного `02_key_generation`: ``new_naive_username``
    возвращает ``[a-z0-9_-]``, ``new_password`` — ``[A-Za-z0-9_-]`` (без
    пробелов и кавычек), поэтому экранирование здесь не требуется.
    ``server.admin_password_hash`` — bcrypt-хеш (алфавит ``[./A-Za-z0-9$]``),
    тоже без пробелов и кавычек.

    Аргументы:
        users: список пользователей панели.
        server: конфигурация сервера (singleton-строка ``ServerConfig``).

    Возвращает:
        Строку Caddyfile, готовую к записи в ``/etc/caddy/Caddyfile``.

    Исключения:
        Не бросает — функция только собирает строку из входных данных.
    """
    basic_auth_lines = [
        f"\t\tbasic_auth {user.naive.username} {user.naive.password}"
        for user in users
        if user.is_active and user.naive is not None
    ]

    lines: list[str] = [
        "{",
        "\t# Caddy собран через xcaddy с модулем github.com/caddyserver/forwardproxy",
        "\torder forward_proxy before reverse_proxy",
        "}",
        "",
        f"{server.domain} {{",
        "\tforward_proxy {",
        *basic_auth_lines,
        "\t\thide_ip",
        "\t\thide_via",
        "\t\tprobe_resistance",
        "\t}",
        '\trespond "Not Found" 404',
        "}",
        "",
        f"{server.admin_domain} {{",
        "\tbasicauth {",
        f"\t\t{server.admin_username} {server.admin_password_hash}",
        "\t}",
        "\treverse_proxy 127.0.0.1:8000",
        "}",
    ]

    return "\n".join(lines) + "\n"