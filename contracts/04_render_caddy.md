# Контракт 04 — render_caddy

Файл: `src/core/render/caddy.py`. Чистая функция.

```python
def render_caddyfile(users: list["User"], server: "ServerConfig") -> str:
    """
    Возвращает содержимое Caddyfile целиком (два site-блока: naive-прокси + админка).
    Учитывает только users с is_active=True и непустым .naive.
    """
```

## Форма результата

```caddyfile
{
	# Caddy собран через xcaddy с модулем github.com/caddyserver/forwardproxy
	order forward_proxy before reverse_proxy
}

<server.domain> {
	forward_proxy {
		basic_auth <NaiveAccount.username 1> <NaiveAccount.password 1>
		basic_auth <NaiveAccount.username 2> <NaiveAccount.password 2>
		hide_ip
		hide_via
		probe_resistance
	}
	respond "Not Found" 404
}

<server.admin_domain> {
	basicauth {
		<server.admin_username> <server.admin_password_hash>
	}
	reverse_proxy 127.0.0.1:8000
}
```

## Инварианты

- Каждый активный `NaiveAccount` → своя строка `basic_auth` внутри блока `forward_proxy` — это позволяет отключать доступ конкретному пользователю без общего пароля.
- Блок `<server.domain> { ... respond "Not Found" 404 }` — обязателен: если запрос пришёл не как CONNECT/forward-proxy, а обычный GET на сайт-домен, Caddy должен отвечать чем-то невзрачным, а не отдавать ошибку, которая выдаёт наличие прокси (часть маскировки Naive).
- Блок админки — **всегда один**, `basicauth` использует уже посчитанный `server.admin_password_hash` (bcrypt), функция не хеширует пароль сама — хеш готовится один раз при `POST /api/setup` через `core/keys` или отдельную утилиту, не при каждом рендере.
- Пустой список naive-аккаунтов → блок `forward_proxy` рендерится без строк `basic_auth` (никто не авторизуется, но синтаксис Caddyfile остаётся валидным) — задача должна явно протестировать этот граничный случай.
