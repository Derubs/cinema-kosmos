"""Общие фикстуры автотестов (pytest): временная БД и клиент Flask."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import src.backend.db as db  # noqa: E402
import src.backend.app as app_module  # noqa: E402


@pytest.fixture()
def temp_db(monkeypatch):
    """Перенаправляет приложение на временную пустую БД и создаёт администратора."""
    db_path = os.path.join(tempfile_dir(), "test_project.db")
    for extension in ("", "-journal", "-wal", "-shm"):
        if os.path.exists(db_path + extension):
            os.remove(db_path + extension)
    # все функции модуля db теперь работают с временным файлом
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db(db_path)
    db.add_user("admin", "admin123", "Администратор Кинотеатра", role="admin")
    yield db_path
    for extension in ("", "-journal", "-wal", "-shm"):
        if os.path.exists(db_path + extension):
            os.remove(db_path + extension)


@pytest.fixture()
def client(temp_db):
    """Flask-клиент с тестовым режимом приложения."""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as test_client:
        yield test_client


def tempfile_dir():
    """Каталог для временных файлов (создаётся при первом обращении)."""
    path = os.path.join(ROOT, "tests", ".tmp")
    os.makedirs(path, exist_ok=True)
    return path
