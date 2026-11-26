"""Проверка целостности ключевых файлов проекта (ЛР 23, задание 2).

Сверяет SHA-256 текущих файлов с эталонными значениями и печатает
результат «OK» или «ИЗМЕНЁН» для каждого файла.

Запуск:  python tools/check_integrity.py
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "tools", "integrity_baseline.json")

FILES = [
    "src/backend/app.py",
    "src/backend/db.py",
    "src/db/schema.sql",
    "src/db/seed.sql",
    "README.md",
    "run.py",
]


def file_hash(path):
    """Возвращает SHA-256-хеш файла."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_hashes():
    """Считает хеши всех контролируемых файлов."""
    return {rel: file_hash(os.path.join(ROOT, rel)) for rel in FILES}


def main():
    """Сверяет текущие хеши с эталоном и возвращает код выхода."""
    if not os.path.exists(BASELINE):
        data = {"created": "эталон", "hashes": current_hashes()}
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Эталон создан: {BASELINE}")
        return 0

    with open(BASELINE, encoding="utf-8") as f:
        baseline = json.load(f)["hashes"]

    changed = 0
    for rel in FILES:
        actual = file_hash(os.path.join(ROOT, rel))
        expected = baseline.get(rel)
        if expected is None:
            print(f"{rel:<26} НОВЫЙ")
            changed += 1
        elif actual == expected:
            print(f"{rel:<26} OK")
        else:
            print(f"{rel:<26} ИЗМЕНЁН")
            changed += 1
    print(f"\nПроверено файлов: {len(FILES)}, изменений: {changed}")
    return 0 if changed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
