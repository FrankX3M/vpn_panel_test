# Контракт 03 — render_singbox

Файл: `src/core/render/singbox.py`. Чистая функция, без сайд-эффектов (не пишет файл — это делает `07_apply_pipeline`).

```python
def render_singbox_config(users: list["User"], server: "ServerConfig") -> dict:
    """
    Возвращает dict, готовый к json.dump в /etc/sing-box/config.json.
    Учитывает только users с is_active=True и непустым .vless / .hysteria2.
    При server пустых обязательных полях (domain, reality_dest, reality_private_key) — raises ValueError.
    """
```

## Форма результата (sing-box v1.9+ схема, проверить актуальность по официальной документации sing-box перед реализацией — версии полей меняются)

```json
{
  "log": {"level": "warn"},
  "inbounds": [
    {
      "type": "vless",
      "tag": "vless-reality-in",
      "listen": "::",
      "listen_port": 2053,
      "users": [
        {"uuid": "<VlessAccount.uuid>", "flow": "xtls-rprx-vision"}
      ],
      "tls": {
        "enabled": true,
        "server_name": "<reality_dest без порта>",
        "reality": {
          "enabled": true,
          "handshake": {"server": "<reality_dest host>", "server_port": "<reality_dest port>"},
          "private_key": "<server.reality_private_key>",
          "short_id": ["<short_id пользователя 1>", "<short_id пользователя 2>", "..."]
        }
      }
    },
    {
      "type": "hysteria2",
      "tag": "hysteria2-in",
      "listen": "::",
      "listen_port": 443,
      "users": [
        {"name": "<label>", "password": "<Hysteria2Account.password>"}
      ],
      "tls": {"enabled": true, "acme": {"domain": ["<server.domain>"], "email": "admin@<server.domain>"}}
    }
  ]
}
```

## Инварианты

- `short_id` в Reality-inbound — **список** всех активных пользователей (не один общий) — так можно отзывать доступ конкретному пользователю без перегенерации ключей у всех.
- `uuid` в списке `users` внутри VLESS-inbound — по одному объекту на активного пользователя с `.vless` аккаунтом.
- Если у Hysteria2-inbound используется ACME на 443/udp — уточнить в задаче, не конфликтует ли с Caddy ACME на 443/tcp за один и тот же домен (обычно нет, ACME challenge идёт по HTTP-01/TLS-ALPN на разных портах/протоколах, но это стоит явно проверить в рамках самого ТЗ, а не считать решённым здесь).
- Пустой список пользователей → `inbounds` всё равно валиден (просто без клиентов) — сервер не должен падать на старте с нулём пользователей.
