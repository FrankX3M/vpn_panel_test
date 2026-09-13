# Контракт 02 — key_generation

Файл: `src/core/keys/generate.py`. Чистые функции, без обращения к БД (принимают/возвращают данные, запись в БД — забота вызывающего кода в `api/`).

```python
def new_vless_uuid() -> str:
    """UUID v4, str(uuid.uuid4())."""

def new_reality_short_id() -> str:
    """8 hex-символов, os.urandom(4).hex()."""

def new_reality_keypair() -> tuple[str, str]:
    """(private_key, public_key) в формате X25519, base64url без padding —
    формат, который ожидает sing-box в config.json (поля private_key/public_key).
    Реализация: cryptography.hazmat.primitives.asymmetric.x25519, либо
    вызов `sing-box generate reality-keypair` через subprocess и парсинг stdout —
    выбрать один способ и явно задокументировать в docstring."""

def new_password(length: int = 24) -> str:
    """URL-safe пароль, secrets.token_urlsafe(length)."""

def new_naive_username(label: str) -> str:
    """Транслитерация label в [a-z0-9_]{3,32}, при коллизии — суффикс -2, -3..."""
```

## Инварианты

- Все функции — `pure` в смысле детерминированности входа/выхода отсутствует (используют `secrets`/`os.urandom`), но **не имеют побочных эффектов** (не пишут в БД, не читают файлы, не логируют).
- `new_reality_keypair()` вызывается **один раз** при первичной настройке сервера (`ServerConfig`), не на каждого пользователя — Reality keypair общий для всего сервера, у пользователя свой только `short_id`.
- `new_naive_username()` должен проверять уникальность — принимает `existing: set[str]` вторым аргументом.

## Что от этого контракта нужно `06_api_users_crud`

При `POST /api/users` эндпоинт вызывает `new_vless_uuid()`, `new_reality_short_id()`, `new_password()` (для Hysteria2), `new_naive_username()` + `new_password()` (для Naive) — и создаёт три связанные записи одним коммитом.
