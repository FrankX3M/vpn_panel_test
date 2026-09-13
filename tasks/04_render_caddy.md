# ТЗ 04 — Render Caddyfile

**Контракт:** `contracts/04_render_caddy.md`
**Зависимости:** `01_db_models`
**Файлы:** `src/core/render/caddy.py`, `tests/core/render/test_caddy.py`

## Задача

Реализовать `render_caddyfile(users, server) -> str` строго по контракту. Два site-блока:
naive-прокси на `server.domain` и reverse_proxy с basic auth на `server.admin_domain`.

## Критерии приёмки

- [ ] Результат содержит блок `<server.domain> { forward_proxy { ... } respond "Not Found" 404 }`.
- [ ] Внутри `forward_proxy` — по одной строке `basic_auth <username> <password>` на каждого
      активного пользователя с `.naive`; неактивные и без `.naive` — отсутствуют.
- [ ] Результат содержит блок `<server.admin_domain> { basicauth { ... } reverse_proxy 127.0.0.1:8000 }`
      с `server.admin_username`/`server.admin_password_hash`.
- [ ] Пустой список naive-аккаунтов → блок `forward_proxy` рендерится без строк `basic_auth`,
      но остаётся синтаксически валидным Caddyfile (проверить хотя бы косвенно — сбалансированные
      скобки, отсутствие пустых директив).
- [ ] Спецсимволы в `label`/`username`/`password` (пробелы, кавычки) не ломают синтаксис Caddyfile —
      либо экранируются, либо генерация username в `02_key_generation` гарантирует безопасный алфавит
      (сослаться явно на то, какой из двух механизмов защищает от инъекции в конфиг).
- [ ] `ruff`/`mypy`/`pytest` проходят.

## Ручная проверка (не только юнит-тесты)

После реализации — прогнать результат через `caddy validate --config <файл> --adapter caddyfile`
(если Caddy установлен в окружении разработки) хотя бы один раз руками, юнит-тесты этого не заменяют.
