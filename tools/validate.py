"""
Независимый финальный контроль качества — запускать отдельно от того, что Cline "уже сделал"
внутри .clinerules. Не дублирование, а проверка, что агент не соврал об успехе.

Запуск: python tools/validate.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"


def run(cmd: list[str]) -> tuple[int, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


def main() -> int:
    print("== ruff ==")
    _, out = run(["ruff", "check", "src", "tests"])
    print(out or "  OK")

    print("\n== mypy ==")
    _, out = run(["mypy", "--ignore-missing-imports", str(SRC)])
    print(out or "  OK")

    print("\n== pytest ==")
    code, out = run(["pytest", "-q"])
    print(out or "  OK")
    if code != 0:
        print("  ❌ тесты упали")
        return 1

    print("\n== manifest ==")
    code, out = run(["python", "tools/validate_manifest.py"])
    print(out)
    if code != 0:
        return 1

    print("\n== mutmut (запустите вручную для критичной логики: mutmut run) ==")
    print("  Цель для core/render и core/svc: mutation score выше 80%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
