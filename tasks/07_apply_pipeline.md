# ТЗ 07 — Apply Pipeline

**Контракт:** `contracts/07_apply_pipeline.md`
**Зависимости:** `03_render_singbox`, `04_render_caddy`, `05_service_control`
**Файлы:** `src/core/apply.py`, `src/core/config.py` (пути констант), `tests/core/test_apply.py`

## Задача

Реализовать `apply(session)` строго по контракту: рендер → temp-файл → `os.replace` → `control(...)`.
В тестах мокать `core.svc.control` и подменять пути `SINGBOX_CONFIG_PATH`/`CADDYFILE_PATH` на
временную директорию (`tmp_path` фикстура pytest) — не писать в реальный `/etc/`.

## Критерии приёмки

- [ ] После `apply()` файл по пути `SINGBOX_CONFIG_PATH` содержит валидный JSON, соответствующий
      состоянию БД на момент вызова.
- [ ] После `apply()` файл по пути `CADDYFILE_PATH` содержит непустую строку.
- [ ] Запись выполняется через `tempfile` + `os.replace` (проверить через мок или через то, что
      файл не оставляет `.tmp`-остатков после успешного выполнения).
- [ ] `control("sing-box", "reload")` и `control("caddy", "reload")` вызваны ровно по разу (мок).
- [ ] Если мок `control` для `caddy` бросает исключение — `apply()` поднимает `ApplyError`,
      файлы на диске при этом уже перезаписаны (откат не выполняется — по контракту).
- [ ] Подключить `apply()` в `06_api_users_crud` — заменить заглушку из ТЗ 06 на реальный вызов
      (интеграция двух ТЗ), обновить/добавить тесты в `tests/api/test_users.py` с моком `control`.
- [ ] `ruff`/`mypy`/`pytest` проходят.

## Это интеграционная точка

После этого ТЗ имеет смысл прогнать `integration_01_e2e.md` — оно первое проверяет цепочку
"создать юзера через API → файлы конфигов валидны → мок systemctl вызван корректно" целиком.
