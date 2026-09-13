# architecture.md — VPN Panel (личное использование + ограниченный круг)

> Легковесная панель управления VPN на одном сервере, без мульти-нод и внешних баз данных.
> Поддерживаемые протоколы: **VLESS+Reality**, **Hysteria2**, **NaiveProxy** — все три поднимаются
> на том же сервере, что и панель. Стек: **Python 3.12 / FastAPI / SQLite / systemd**, без Docker.

---

## 1. Цель и нефункциональные ограничения

- Один сервер, один админ (может быть 2-3, см. `ServerConfig.admin_*`).
- До ~30-50 пользователей — SQLite достаточно, Postgres избыточен.
- Никаких лимитов трафика и сроков действия — только `is_active: bool` (по решению из диалога).
- Никаких мульти-нод, кластеров, очередей задач — конфиг генерится синхронно, применяется через `systemctl reload`.
- Админка **открыта наружу**, но защищена Basic Auth на уровне Caddy (см. раздел 4) — панель сама не реализует логин/сессии, это не её ответственность.

## 2. Компоненты рантайма (что крутится на сервере)

| Процесс | systemd-юнит | Роль | Порт |
|---|---|---|---|
| VPN Panel (FastAPI) | `vpn-panel.service` | CRUD пользователей, рендер конфигов, дергает systemctl | `127.0.0.1:8000` (только localhost) |
| sing-box | `sing-box.service` (upstream) | VLESS+Reality inbound + Hysteria2 inbound | `2053/tcp` (Reality), `443/udp` (Hysteria2) |
| Caddy (с модулем `forwardproxy`) | `caddy.service` (upstream, кастомная сборка через xcaddy) | NaiveProxy inbound + reverse-proxy на панель с Basic Auth | `443/tcp` |

Панель никогда не слушает наружу напрямую — весь внешний HTTPS-трафик на 443/tcp принимает Caddy и либо обслуживает как naive-прокси, либо реверс-проксирует на `127.0.0.1:8000` с Basic Auth для админ-хоста.

## 3. Схема потоков данных

```
Admin (браузер) ──HTTPS+BasicAuth──▶ Caddy (443/tcp, host: panel.example.com)
                                          │ reverse_proxy
                                          ▼
                                 vpn-panel.service (127.0.0.1:8000)
                                          │
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                 core/db (SQLite)   core/render        core/svc
                 users, accounts    → sing-box JSON     → systemctl reload
                                    → Caddyfile           sing-box / caddy
```

```
Client (VLESS)  ──TCP 2053, Reality handshake──▶ sing-box.service
Client (Hysteria2) ──UDP 443──▶ sing-box.service
Client (Naive)  ──HTTPS 443, host: example.com──▶ Caddy (forwardproxy)
```

Один физический сервер, один домен `example.com` (для Naive и Reality-фасада) + один поддомен
`panel.example.com` (для админки) — оба резолвятся на один и тот же IP, разруливает их Caddy по SNI/Host.

## 4. Почему порты именно такие

- **443/tcp → Caddy**, не sing-box. Naive обязан выглядеть как настоящий HTTPS-сайт с валидным
  ACME-сертификатом — в этом суть маскировки протокола. Caddy сам получает сертификат по ACME.
- **2053/tcp → sing-box (Reality)**. Reality не требует именно 443 — его маскировка построена на
  проксировании чужого TLS-рукопожатия (`reality_dest`), а не на занятости стандартного порта.
  Если посадить Reality тоже на 443, придётся ставить SNI-мультиплексор (sslh / nginx stream) —
  лишний процесс и лишний конфиг, что прямо противоречит требованию "без сложных нод".
- **443/udp → sing-box (Hysteria2)**. QUIC живёт в отдельном адресном пространстве от TCP, конфликта
  с Caddy на 443/tcp нет.
- **panel.example.com → Caddy → 127.0.0.1:8000**. Панель никогда не открыта в интернет напрямую;
  Caddy — единственная точка входа снаружи, и единственный процесс, который слушает публичные порты.

## 5. Модель данных (контракт, детали — `contracts/01_db_models.md`)

```
User (1) ── (0..1) VlessAccount
           ── (0..1) Hysteria2Account
           ── (0..1) NaiveAccount
ServerConfig — singleton-строка с доменами, ключами Reality, Basic Auth админки
```

При создании `User` панель сразу создаёт все три аккаунта — админ не щёлкает три формы.
Отключение = `User.is_active = False` → пользователь пропадает из следующего рендера конфигов.

## 6. Модуль `core/render` — чистые функции

```python
def render_singbox_config(users: list[User], server: ServerConfig) -> dict: ...
def render_caddyfile(users: list[User], server: ServerConfig) -> str: ...
```

Без сайд-эффектов, без обращения к БД внутри — вход "список активных юзеров + конфиг сервера",
выход "готовая структура/строка конфига". Это тот код, который проще всего покрыть тестами
отдельной сессией Cline (риск ложной уверенности из пайплайн-гайда: рендер — чистая функция,
легко подсунуть заведомо кривой `ServerConfig` и проверить поведение на границе).

## 7. Модуль `core/svc` — единственная точка, где панель трогает систему

```python
ALLOWED_SERVICES = {"sing-box", "caddy"}
ALLOWED_ACTIONS = {"restart", "reload", "status"}

def control(service: str, action: str) -> subprocess.CompletedProcess: ...
```

Панель работает от отдельного системного пользователя `vpn-panel` (не root), с sudoers-правилом,
ограниченным ровно двумя юнитами и тремя действиями (см. `deploy/install.sh`). Это единственный
файл в проекте, который стоит прочитать глазами перед мержем — весь остальной код может писать
LLM без построчного ревью.

## 8. Флоу "добавить пользователя"

1. Admin вызывает `POST /api/users` (`{"label": "Вася"}`).
2. `api/users.py` создаёт `User`, вызывает `core/keys` → генерит UUID/short_id (Reality),
   пароль (Hysteria2), логин+пароль (Naive).
3. Admin вызывает `POST /api/apply` (или это происходит автоматически внутри создания —
   решается в `07_apply_pipeline`).
4. `core/render.render_singbox_config()` + `render_caddyfile()` → пишут файлы в
   `/etc/sing-box/config.json` и `/etc/caddy/Caddyfile`.
5. `core/svc.control("sing-box", "reload")` + `control("caddy", "reload")`.
6. Панель отдаёт готовые ссылки: `vless://...#label`, `hysteria2://...#label`,
   `naive+https://user:pass@example.com` — плюс QR-код на каждую (`08_client_links`).

## 9. Структура репозитория

```
vpn-panel/
├── architecture.md          ← этот файл
├── manifest.json             ← граф ТЗ и зависимостей (для validate_manifest.py)
├── .clinerules                ← правила для Cline
├── contracts/                 ← общие контракты (схемы, сигнатуры) — вход в контекст-пакет каждого ТЗ
├── tasks/                      ← самодостаточные ТЗ, по одному на файл
├── tools/
│   ├── validate_manifest.py   ← сверяет manifest.json с contracts/ и tasks/
│   └── validate.py             ← независимый прогон ruff/mypy/pytest
├── deploy/
│   ├── install.sh               ← bootstrap: sing-box, caddy+forwardproxy, systemd, sudoers
│   └── systemd/vpn-panel.service
├── src/
│   ├── api/                     ← FastAPI-роуты
│   ├── core/db/                 ← SQLAlchemy-модели, сессии
│   ├── core/keys/                ← генерация UUID/Reality-ключей/паролей
│   ├── core/render/               ← чистые функции рендера конфигов
│   ├── core/svc/                   ← systemctl-обёртка
│   └── web/templates/               ← Jinja2-страницы админки
└── tests/
```

## 10. Явно вне рамок (не делаем)

- Мульти-нода / несколько серверов под одной панелью — если понадобится, это отдельный проект.
- Учёт трафика на пользователя — по решению из диалога, не нужен на старте.
- Авто-обновление sing-box/caddy из панели — обновляется руками через `apt`/бинарник, panel этого не касается.
- OAuth/2FA для админки — Basic Auth от Caddy достаточен для одного-двух админов; если станет
  мало, это отдельное ТЗ поверх текущей архитектуры, а не пересмотр её.
