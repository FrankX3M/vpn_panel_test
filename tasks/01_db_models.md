# ТЗ 01 — DB Models

**Контракт:** `contracts/01_db_models.md`
**Зависимости:** нет
**Файлы к созданию:** `src/core/db/models.py`, `src/core/db/session.py`, `tests/core/db/test_models.py`

## Задача

Реализовать SQLAlchemy-модели строго по контракту `01_db_models.md`: `User`, `VlessAccount`,
`Hysteria2Account`, `NaiveAccount`, `ServerConfig`. Плюс `src/core/db/session.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine("sqlite:///./vpn_panel.db")
SessionLocal = sessionmaker(bind=engine)

def init_db() -> None:
    """Base.metadata.create_all(engine) — вызывается один раз при старте приложения."""
```

## Критерии приёмки

- [ ] Все поля и типы соответствуют контракту дословно.
- [ ] `cascade="all, delete-orphan"` работает: удаление `User` удаляет связанные аккаунты (тест).
- [ ] `init_db()` создаёт файл `vpn_panel.db` и все таблицы без ошибок на чистой БД.
- [ ] Тест: создание `User` без явного `is_active` → `is_active == True` (дефолт).
- [ ] Тест: создание `ServerConfig` с `id=1` дважды → второй insert либо падает (UNIQUE), либо
      логика уникальности singleton проверяется на уровне `06_api_users_crud` (уточнить в коде
      комментарием, где именно обеспечивается инвариант "ровно одна строка").
- [ ] `ruff check` и `mypy --ignore-missing-imports` проходят без ошибок.

## Не входит в это ТЗ

Генерация значений полей (UUID, ключи, пароли) — это `02_key_generation`. Здесь модели должны
принимать эти значения как обычные параметры конструктора.
