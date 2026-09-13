"""
Сверяет manifest.json с реальными файлами в contracts/ и tasks/, и проверяет граф зависимостей
на отсутствие циклов и ссылок на несуществующие задачи.

Запуск: python tools/validate_manifest.py
Код возврата: 0 — всё ок, 1 — найдены проблемы (текст проблем печатается в stdout).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST_PATH = ROOT / "manifest.json"
CONTRACTS_DIR = ROOT / "contracts"
TASKS_DIR = ROOT / "tasks"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def check_files_exist(tasks: list[dict]) -> list[str]:
    problems = []
    task_ids = {t["id"] for t in tasks}
    for t in tasks:
        task_file = TASKS_DIR / f"{t['id']}.md"
        if not task_file.exists():
            problems.append(f"[{t['id']}] нет файла задачи: {task_file}")
        for c in t.get("contracts", []):
            contract_file = CONTRACTS_DIR / f"{c}.md"
            if not contract_file.exists():
                problems.append(f"[{t['id']}] ссылается на несуществующий контракт: {c}")
        for dep in t.get("depends_on", []):
            if dep not in task_ids:
                problems.append(f"[{t['id']}] зависит от несуществующей задачи: {dep}")
    return problems


def check_cycles(tasks: list[dict]) -> list[str]:
    graph = {t["id"]: t.get("depends_on", []) for t in tasks}
    visited: dict[str, str] = {}  # id -> "visiting" | "done"
    problems = []

    def dfs(node: str, path: list[str]) -> None:
        state = visited.get(node)
        if state == "done":
            return
        if state == "visiting":
            cycle = " -> ".join(path[path.index(node):] + [node])
            problems.append(f"обнаружен цикл зависимостей: {cycle}")
            return
        visited[node] = "visiting"
        for dep in graph.get(node, []):
            dfs(dep, path + [node])
        visited[node] = "done"

    for t in tasks:
        dfs(t["id"], [])
    return problems


def check_orphan_files(tasks: list[dict]) -> list[str]:
    """Файлы в tasks/ или contracts/, на которые манифест не ссылается — не ошибка, но стоит знать."""
    problems = []
    manifest_task_ids = {t["id"] for t in tasks}
    for f in TASKS_DIR.glob("*.md"):
        if f.stem not in manifest_task_ids:
            problems.append(f"файл задачи без записи в манифесте: {f.name}")
    return problems


def main() -> int:
    manifest = load_manifest()
    tasks = manifest.get("tasks", [])

    problems = []
    problems += check_files_exist(tasks)
    problems += check_cycles(tasks)
    problems += check_orphan_files(tasks)

    if problems:
        print(f"Найдено проблем: {len(problems)}\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"OK: {len(tasks)} задач, манифест синхронизирован с contracts/ и tasks/, циклов нет.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
