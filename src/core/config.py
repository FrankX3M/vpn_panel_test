"""Пути к боевым конфигам (контракт `07_apply_pipeline.md`).

Константы вынесены в отдельный модуль, чтобы путь не хардкодился строкой в
нескольких местах и чтобы тесты могли подменять его через monkeypatch.
"""

SINGBOX_CONFIG_PATH = "/etc/sing-box/config.json"
CADDYFILE_PATH = "/etc/caddy/Caddyfile"