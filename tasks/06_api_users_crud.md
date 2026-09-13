# ТЗ 06 — API Users CRUD

**Контракт:** `contracts/06_api_users_crud.md`
**Зависимости:** `01_db_models`, `02_key_generation` (пока БЕЗ `07_apply_pipeline` — на этом шаге вызов
`apply()` можно замокать/заглушить, интеграция реального применения — в `07`, чтобы не блокировать
это ТЗ ожиданием готовности рендера).
**Файлы:** `src/api/users.py`, `src/api/schemas.py`, `src/main.py` (точка входа FastAPI, если ещё не создана), `tests/api/test_users.py`

## Задача

Реализовать эндпоинты из контракта. Использовать `fastapi.testclient.TestClient` + временную SQLite
БД (`sqlite:///./test.db` или `sqlite:///:memory:` с `StaticPool`, если нужны множественные сессии
в одном соединении) для тестов — не трогать боевую `vpn_panel.db`.

Вызов пайплайна применения конфигов (`core.apply.apply(session)`) — сделать через **инъекцию
зависимости** (FastAPI `Depends`) с возможностью подмены в тестах на no-op заглушку, чтобы тесты
этого ТЗ не зависели от готовности `07_apply_pipeline` и не пытались реально дёргать `systemctl`.

## Критерии приёмки

- [ ] `POST /api/setup` дважды → второй раз 409.
- [ ] `POST /api/users {"label": "Вася"}` → 201, в БД появился `User` + 3 связанных аккаунта с непустыми полями.
- [ ] `GET /api/users` → список без приватных полей аккаунтов (только `id, label, is_active, created_at`).
- [ ] `GET /api/users/{id}` → включает данные аккаунтов (для последующего использования в `08`).
- [ ] `PATCH /api/users/{id} {"is_active": false}` → 200, поле обновлено.
- [ ] `DELETE /api/users/{id}` → 204, юзер и все аккаунты удалены из БД.
- [ ] `GET/PATCH/DELETE` на несуществующий `id` → 404.
- [ ] `ruff`/`mypy`/`pytest` проходят.
