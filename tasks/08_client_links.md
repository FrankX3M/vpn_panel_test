# ТЗ 08 — Client Links & QR

**Контракт:** `contracts/08_client_links.md`
**Зависимости:** `01_db_models`
**Файлы:** `src/core/render/links.py`, `tests/core/render/test_links.py`
**Новая зависимость проекта:** добавить `segno` в `requirements.txt`/`pyproject.toml`.

## Задача

Реализовать `vless_link`, `hysteria2_link`, `naive_link`, `qr_svg` строго по контракту.

## Критерии приёмки

- [ ] `vless_link` для юзера с `.vless` → строка начинается с `vless://`, содержит `uuid`, `sid=`,
      `pbk=`, корректно закодированный `label` в `#`-фрагменте (кириллица → percent-encoding).
- [ ] `vless_link` для юзера БЕЗ `.vless` → возвращает `None`, не бросает исключение.
- [ ] Аналогично для `hysteria2_link`/`naive_link`.
- [ ] `qr_svg("любая непустая строка")` → возвращает непустую строку, начинающуюся с `<svg`.
- [ ] `ruff`/`mypy`/`pytest` проходят.
