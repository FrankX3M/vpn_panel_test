# Контракт 06 — api_users_crud

Файл: `src/api/users.py`. Опирается на `01_db_models`, `02_key_generation`.

## Эндпоинты

```
POST   /api/setup                → создать ServerConfig (один раз; 409 если уже существует)
GET    /api/server-config        → текущий ServerConfig (без приватных ключей в ответе)
POST   /api/users                → {"label": str} → создаёт User + 3 аккаунта, применяет конфиги (07)
GET    /api/users                → list[UserOut]
GET    /api/users/{id}           → UserOut (с ссылками, см. 08_client_links)
PATCH  /api/users/{id}           → {"is_active": bool} → применяет конфиги (07)
DELETE /api/users/{id}           → каскадное удаление, применяет конфиги (07)
```

## Pydantic-схемы (набросок, финализируется в самом ТЗ)

```python
class UserCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)

class UserOut(BaseModel):
    id: int
    label: str
    is_active: bool
    created_at: datetime
```

## Инварианты

- Любая мутация (`POST /users`, `PATCH`, `DELETE`) в конце вызывает `apply_pipeline()` (контракт 07) — рассинхронизации между БД и живыми конфигами быть не должно; ручной кнопки "применить" в API нет (по решению — минимальная реализация).
- Все ответы — только через `UserOut`, приватные поля аккаунтов (`uuid`, пароли) отдаются исключительно через `GET /api/users/{id}` в явном виде для копирования — не через списочный `GET /api/users`.
