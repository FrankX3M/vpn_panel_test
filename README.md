# VPN Panel

Легковесная панель управления VPN на одном сервере: VLESS+Reality, Hysteria2, NaiveProxy.
Для личного использования + ограниченного круга людей, без мульти-нод.

## С чего начать (в Cline)

1. Открой эту папку как проект в VS Code, установи Cline (см. `docs/llm-code-pipeline-*.md`,
   если он у тебя есть отдельно — там инструкция по настройке Cline+Continue+DeepSeek).
2. Прочитай `architecture.md` — это общая карта проекта.
3. Прогони `python tools/validate_manifest.py` — убедиться, что манифест синхронизирован
   (на старте должен быть чистый OK).
4. Открывай задачи по порядку зависимостей из `manifest.json`, начиная с тех, у кого
   `depends_on: []` — сейчас это `01_db_models`, `02_key_generation`, `05_service_control`
   (их можно делать параллельно/в любом порядке).
5. Для каждой задачи: дай Cline соответствующий файл из `tasks/*.md` + контракт(ы), на которые
   он ссылается, из `contracts/`. Дождись плана (Plan-режим), одобри, дай выполнить.
6. После каждой задачи — `python tools/validate.py` как независимая проверка.
7. `05_service_control` — обязательно ручное ревью после генерации, см. пометку в `.clinerules`.

## Локальный запуск (после того как код появится)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Деплой на сервер

```bash
sudo bash deploy/install.sh
```

Дальше — скопировать код в `/opt/vpn-panel`, поставить зависимости в venv, запустить
`vpn-panel.service` (юнит уже устанавливается скриптом). Подробности — `architecture.md`, разделы 2 и 9.

## Структура

См. `architecture.md`, раздел 9 — там разбор всех директорий.
