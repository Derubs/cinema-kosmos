"""Точка входа веб-приложения «Онлайн-кинотеатр „Космос"».

Запуск: python run.py
Приложение доступно по адресу http://127.0.0.1:5000
"""
from src.backend.app import app

if __name__ == "__main__":
    # debug=False, чтобы сервер работал стабильно как «продукт»
    app.run(host="127.0.0.1", port=5000, debug=False)
