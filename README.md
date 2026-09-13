# VPN Panel

Лёгкая панель управления VPN на одном сервере — без мульти-нод, без внешних баз данных,
для личного использования и небольшого круга людей.

Поддерживаемые протоколы, все на одном сервере вместе с панелью:

- **VLESS + Reality** (через [sing-box](https://sing-box.sagernet.org/))
- **Hysteria2** (через sing-box)
- **NaiveProxy** (через [Caddy](https://caddyserver.com/) с модулем [forwardproxy](https://github.com/klzgrad/forwardproxy))

Стек: Python 3.12 / FastAPI / SQLAlchemy / SQLite / systemd. Без Docker.

---

## Требования

- Чистый сервер на Ubuntu/Debian (проверялось на Debian 13 "trixie") с root-доступом.
- Домен с двумя A-записями, указывающими на IP сервера:
  - `example.com` — для NaiveProxy и Reality-фасада;
  - `panel.example.com` — для веб-админки.

  Без действующих DNS-записей Caddy не сможет выпустить TLS-сертификаты через ACME.

- Порт **443/tcp** (NaiveProxy + reverse-proxy на админку через Caddy) и **443/udp**
  (Hysteria2 через sing-box) должны быть свободны и открыты в файрволе/security group
  твоего хостинга. Reality слушает **2053/tcp** — тоже должен быть открыт.

---

## Быстрый старт

### 1. Склонировать репозиторий на сервер

```bash
git clone https://github.com/<твой-форк>/vpn_panel.git /opt/vpn-panel
cd /opt/vpn-panel
```

> Путь `/opt/vpn-panel` захардкожен в `deploy/systemd/vpn-panel.service` — если хочешь
> развернуть в другую директорию, замени `/opt/vpn-panel` на свой путь во всех трёх
> местах юнита (`WorkingDirectory`, `PATH`, `ExecStart`) **до** запуска установки.

### 2. Установить системные зависимости

```bash
sudo bash deploy/install.sh
```

Скрипт ставит sing-box, Go-тулчейн, собирает Caddy с модулем `forwardproxy` через `xcaddy`,
создаёт системных пользователей `vpn-panel`/`caddy` с ограниченными правами, кладёт
systemd-юниты. Скрипт идемпотентен — безопасно запускать повторно.

### 3. Установить Python-зависимости панели

```bash
sudo -u vpn-panel bash -c "
  cd /opt/vpn-panel
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
"
```

### 4. Запустить все три сервиса

```bash
sudo systemctl enable --now vpn-panel
sudo systemctl enable --now sing-box
sudo systemctl enable --now caddy
```

На этом шаге `caddy`, скорее всего, будет падать (`failed`) — это ожидаемо: Caddyfile
ещё не сгенерирован, он появится после первой настройки панели на следующем шаге.

### 5. Настроить панель через Swagger UI

Панель слушает только `127.0.0.1:8000` — наружу её отдаёт Caddy. Для первой настройки
удобнее всего пробросить порт по SSH:

```bash
ssh -L 8000:127.0.0.1:8000 root@<IP_сервера>
```

Открой в браузере `http://127.0.0.1:8000/docs` — это Swagger UI со всеми эндпоинтами.

Сгенерируй bcrypt-хеш пароля админки (Caddy `basicauth` не принимает пароль в открытом виде):

```bash
caddy hash-password --plaintext '<придумай пароль>'
```

Выполни `POST /api/setup` с телом:

```json
{
  "domain": "example.com",
  "admin_domain": "panel.example.com",
  "admin_username": "admin",
  "admin_password_hash": "<вывод caddy hash-password>",
  "reality_dest": "www.microsoft.com:443"
}
```

`reality_dest` — любой реальный HTTPS-сайт, который будет "маскировочной" целью для Reality
(должен отвечать на TLS ClientHello так же, как настоящий популярный сайт — это часть
механизма маскировки протокола, менять на что-то экзотическое не стоит).

Ответ **201** означает, что `ServerConfig` создан, а панель уже сгенерировала и применила
первые конфиги для sing-box и Caddy.

### 6. Создать первого пользователя

Через тот же Swagger (`POST /api/users`) или через веб-форму `http://127.0.0.1:8000/users/new`:

```json
{"label": "мой ноут"}
```

Ответ содержит готовые ссылки для клиентов:
- `vless://...` — для VLESS+Reality (v2rayN, NekoBox, sing-box клиенты и т.п.);
- `hysteria2://...` — для Hysteria2;
- `naive+https://...` — для NaiveProxy.

### 7. Дальше — веб-админка

`https://panel.example.com` (тот самый `admin_domain`) — обычная страница с Basic Auth
(логин/пароль из шага 5), список пользователей, создание/включение/выключение/удаление,
ссылки и QR-коды на карточке каждого пользователя.

---

## Как это устроено

```
Клиент (браузер/приложение) ──HTTPS──▶ Caddy (443/tcp)
                                          │
                          ┌───────────────┼──────────────────┐
                          ▼ (Host: example.com)      ▼ (Host: panel.example.com)
                   forward_proxy (Naive)      reverse_proxy → 127.0.0.1:8000 (панель)

Клиент (VLESS) ──TCP 2053, Reality handshake──▶ sing-box
Клиент (Hysteria2) ──UDP 443──▶ sing-box
```

Панель — тонкий слой поверх systemd: создание/изменение/удаление пользователя рендерит
`/etc/sing-box/config.json` и `/etc/caddy/Caddyfile` из состояния БД и применяет их через
`systemctl reload`/`restart`. Никакого рантайм-API движков не используется — источник истины
всегда SQLite, конфиги генерируются заново при каждом изменении.

Подробности реализации — читай код в `src/`, он небольшой и прокомментирован.

---

## Структура репозитория

```
vpn-panel/
├── deploy/
│   ├── install.sh                 ← установка sing-box/Go/Caddy, системные юзеры, sudoers
│   └── systemd/
│       ├── vpn-panel.service
│       └── caddy.service
├── src/
│   ├── main.py                    ← точка входа FastAPI
│   ├── api/                       ← REST-эндпоинты (/api/setup, /api/users, ...)
│   ├── core/
│   │   ├── db/                    ← SQLAlchemy-модели, сессия, init_db()
│   │   ├── keys/                  ← генерация UUID/Reality-ключей/паролей
│   │   ├── render/                ← рендер sing-box config.json / Caddyfile / клиентских ссылок
│   │   ├── svc/                   ← systemctl-обёртка (whitelist сервисов/действий)
│   │   └── apply.py               ← рендер → запись файлов → reload/restart сервисов
│   └── web/                       ← веб-админка (Jinja2)
├── tests/                         ← pytest, покрывает core/ и api/
├── requirements.txt
└── pyproject.toml                 ← настройки ruff/mypy/pytest
```

## Тесты

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
ruff check src/ tests/
mypy --ignore-missing-imports src/
```

## Известные ограничения

- Один сервер, без мульти-нод и без учёта трафика на пользователя (только вкл/выкл).
- Веб-админка защищена только Basic Auth на уровне Caddy — для одного-двух админов
  этого достаточно; для большего числа людей стоит добавить OAuth/2FA отдельно.
- `POST /api/setup` можно вызвать только один раз (повторный вызов → 409); если нужно
  изменить домен/ключи Reality после первой настройки — редактируй `ServerConfig` напрямую
  в БД либо расширяй API отдельным `PATCH`-эндпоинтом.
