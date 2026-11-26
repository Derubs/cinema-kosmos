"""Создание базы данных project.db с тестовыми данными (ЛР 14).

Запуск: python src/db/seed_db.py
Скрипт создаёт пустые таблицы по schema.sql и наполняет их
тестовыми данными из seed.sql. Повторный запуск начинает с нуля.
"""
import os
import sqlite3

HERE = os.path.dirname(__file__)
DB_PATH = os.path.join(HERE, "project.db")


def seed():
    """Пересоздаёт БД: схема + тестовые данные."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    with open(os.path.join(HERE, "schema.sql"), "r", encoding="utf-8") as f:
        schema = f.read()
    with open(os.path.join(HERE, "seed.sql"), "r", encoding="utf-8") as f:
        seed_data = f.read()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.executescript(seed_data)
        conn.commit()
        print("База данных создана:", os.path.abspath(DB_PATH))
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
