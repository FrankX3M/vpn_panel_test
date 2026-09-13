# Контракт 08 — client_links

Файл: `src/core/render/links.py`. Опирается на `01_db_models`.

```python
def vless_link(user: "User", server: "ServerConfig") -> str:
    """
    vless://<uuid>@<server.domain>:2053?security=reality&sni=<reality_dest_host>
    &fp=chrome&pbk=<reality_public_key>&sid=<short_id>&flow=xtls-rprx-vision&type=tcp#<label>
    """

def hysteria2_link(user: "User", server: "ServerConfig") -> str:
    """
    hysteria2://<password>@<server.domain>:443/?sni=<server.domain>#<label>
    """

def naive_link(user: "User", server: "ServerConfig") -> str:
    """
    naive+https://<username>:<password>@<server.domain>:443#<label>
    """

def qr_svg(data: str) -> str:
    """SVG-код QR по строке ссылки, библиотека `segno` (легче, чем qrcode+Pillow, чистый Python)."""
```

## Инварианты

- Если у `User` нет соответствующего аккаунта (например, `.vless is None`) — функция возвращает `None`, а не бросает исключение (страница админки просто не показывает эту ссылку).
- URL-энкодинг всех параметров через `urllib.parse.quote` — `label` может содержать кириллицу/пробелы.
