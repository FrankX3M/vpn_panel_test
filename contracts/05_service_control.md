# Контракт 05 — service_control

Файл: `src/core/svc/control.py`. **Критичная логика — обязательно ручное ревью после генерации Cline, не полагаться на зелёные тесты.**

```python
ALLOWED_SERVICES: frozenset[str] = frozenset({"sing-box", "caddy"})
ALLOWED_ACTIONS: frozenset[str] = frozenset({"restart", "reload", "status"})

class ServiceControlError(Exception): ...

def control(service: str, action: str) -> subprocess.CompletedProcess:
    """
    Выполняет `sudo systemctl <action> <service>`.
    Raises ServiceControlError если service/action не входят в whitelist —
    проверка ДО формирования команды, никакой конкатенации сырых строк в shell=True.
    Использует subprocess.run(["sudo", "systemctl", action, service], capture_output=True, timeout=10).
    НЕ shell=True. НЕ f-строка, собранная из внешнего ввода, напрямую в команду.
    """
```

## Инварианты (не подлежат "оптимизации" агентом)

- `shell=False` всегда — команда передаётся списком аргументов, никогда строкой.
- Валидация `service in ALLOWED_SERVICES` и `action in ALLOWED_ACTIONS` — **до** сборки команды, не после.
- `timeout` обязателен — panel не должна зависнуть навечно, если systemctl подвис.
- Пользователь ОС, от которого работает `vpn-panel.service`, имеет право на `sudo systemctl {restart,reload,status} {sing-box,caddy}` **и ничего больше** — это настраивается в `deploy/install.sh` через файл в `/etc/sudoers.d/`, не через общий `visudo` с широкими правами.
- Эта функция не принимает произвольный `service`/`action` из HTTP-запроса напрямую — вызывающий код в `api/` может дёргать `control()` только с захардкоженными в самом коде панели строками, никогда не прокидывая пользовательский ввод в эти параметры.
