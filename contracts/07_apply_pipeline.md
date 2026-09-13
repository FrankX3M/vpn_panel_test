# Контракт 07 — apply_pipeline

Файл: `src/core/apply.py`. Опирается на `03_render_singbox`, `04_render_caddy`, `05_service_control`.

```python
def apply(session: "Session") -> None:
    """
    1. users = все User (все, не только активные — фильтрация по is_active внутри render-функций).
    2. server = единственный ServerConfig.
    3. singbox_json = render_singbox_config(users, server)
    4. caddyfile = render_caddyfile(users, server)
    5. Пишет во временные файлы, затем os.replace() на целевой путь (атомарная замена,
       чтобы reload не подхватил наполовину записанный файл).
    6. control("sing-box", "reload"); control("caddy", "reload")
    7. Если reload одного из сервисов упал (returncode != 0) — поднимает ApplyError
       с текстом stderr, НЕ откатывает файлы автоматически (откат — ручное действие админа,
       чтобы не городить сложную транзакционность ради 1-2 пользователей).
    """
```

## Пути файлов (константы, не хардкодить строкой в нескольких местах — вынести в `src/core/config.py`)

```python
SINGBOX_CONFIG_PATH = "/etc/sing-box/config.json"
CADDYFILE_PATH = "/etc/caddy/Caddyfile"
```

## Инварианты

- Запись файла — всегда через temp-file + `os.replace`, никогда прямой `open(path, "w")` поверх боевого конфига.
- `apply()` вызывается синхронно внутри HTTP-запроса (создание/изменение/удаление юзера) — при таком масштабе (до полусотни пользователей) рендер и reload укладываются в доли секунды, отдельная очередь задач не нужна.
- Ошибка `ApplyError` должна долетать до API-слоя как HTTP 500 с телом, содержащим stderr systemctl — админ должен сразу видеть, что именно сломалось (например, невалидный Caddyfile), а не получать голый 500.
