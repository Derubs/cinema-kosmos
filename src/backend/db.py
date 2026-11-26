"""Модуль работы с базой данных онлайн-кинотеатра «Космос».

Содержит подключение к SQLite (ЛР 15) и функции CRUD
для фильмов, сеансов и билетов (ЛР 16-17).
"""
import hashlib
import logging
import os
import sqlite3

# Путь к базе данных: src/db/project.db относительно корня проекта
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "project.db")

# Размер зала: 5 рядов по 10 мест (используется на схеме зала)
HALL_ROWS = 5
HALL_SEATS = 10


def get_connection(db_path=None):
    """Открывает соединение с базой данных (ЛР 15).

    :param db_path: путь к файлу БД (по умолчанию project.db)
    :return: объект sqlite3.Connection с включённым проверкой внешних ключов
    """
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path=None):
    """Создаёт таблицы по скрипту schema.sql (ЛР 14).

    Используется при первичном запуске и в автотестах.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        script = f.read()
    conn = get_connection(db_path)
    conn.executescript(script)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------
# Пользователи и авторизация (ЛР 19)
# ---------------------------------------------------------------

def hash_password(password):
    """Возвращает SHA-256 хеш пароля — пароли не хранятся открыто."""
    return hashlib.sha256(password.encode()).hexdigest()


def add_user(login, password, fio, role="client"):
    """Регистрирует нового пользователя. Возвращает True при успехе."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (login, password_hash, fio, role) VALUES (?, ?, ?, ?)",
            (login, hash_password(password), fio, role),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # логин уже занят (поле login UNIQUE)
        return False
    finally:
        conn.close()


def find_user_by_login(login):
    """Ищет пользователя по логину. Возвращает строку (id, login, hash, fio, role)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, login, password_hash, fio, role FROM users WHERE login = ?",
        (login,),
    ).fetchone()
    conn.close()
    return row


def check_login(login, password):
    """Проверяет логин и пароль. Возвращает (id, role) или None (ЛР 19)."""
    user = find_user_by_login(login)
    if user and user[2] == hash_password(password):
        return user[0], user[4]
    return None


# ---------------------------------------------------------------
# Фильмы (CRUD, ЛР 16-17)
# ---------------------------------------------------------------

def get_films():
    """Возвращает список всех фильмов репертуара."""
    conn = get_connection()
    films = conn.execute(
        "SELECT id, title, genre, duration_min, age_rating, description "
        "FROM films ORDER BY title"
    ).fetchall()
    conn.close()
    return films


def get_film(film_id):
    """Возвращает один фильм по id или None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, title, genre, duration_min, age_rating, description "
        "FROM films WHERE id = ?",
        (film_id,),
    ).fetchone()
    conn.close()
    return row


def add_film(title, genre, duration_min, age_rating, description=""):
    """Добавляет фильм в афишу. Возвращает True при успехе."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO films (title, genre, duration_min, age_rating, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, genre, duration_min, age_rating, description),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError as err:
        logging.error("Ошибка добавления фильма: %s", err)
        return False
    finally:
        conn.close()


def update_film(film_id, title, genre, duration_min, age_rating, description):
    """Редактирует данные фильма (операция Update, ЛР 17)."""
    conn = get_connection()
    conn.execute(
        "UPDATE films SET title = ?, genre = ?, duration_min = ?, "
        "age_rating = ?, description = ? WHERE id = ?",
        (title, genre, duration_min, age_rating, description, film_id),
    )
    conn.commit()
    conn.close()


def delete_film(film_id):
    """Удаляет фильм. Если у фильма есть сеансы — запрещает удаление."""
    conn = get_connection()
    sessions_count = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE film_id = ?", (film_id,)
    ).fetchone()[0]
    if sessions_count > 0:
        conn.close()
        return False  # нельзя удалить фильм с сеансами (ошибка внешнего ключа)
    conn.execute("DELETE FROM films WHERE id = ?", (film_id,))
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------
# Киносеансы (CRUD, ЛР 16-17)
# ---------------------------------------------------------------

def get_sessions(film_id=None):
    """Возвращает сеансы с данными фильма (JOIN). Можно фильтровать по фильму."""
    conn = get_connection()
    sql = (
        "SELECT s.id, s.start_time, s.hall, s.price, f.title, f.genre, "
        "f.duration_min, f.age_rating "
        "FROM sessions s JOIN films f ON s.film_id = f.id "
    )
    params = ()
    if film_id:
        sql += "WHERE s.film_id = ? "
        params = (film_id,)
    sql += "ORDER BY s.start_time"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows


def get_session(session_id):
    """Возвращает один сеанс с данными фильма по id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT s.id, s.start_time, s.hall, s.price, f.title, f.genre, "
        "f.duration_min, f.age_rating "
        "FROM sessions s JOIN films f ON s.film_id = f.id WHERE s.id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    return row


def add_session(film_id, start_time, hall, price):
    """Добавляет сеанс в расписание. Возвращает True при успехе."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO sessions (film_id, start_time, hall, price) "
            "VALUES (?, ?, ?, ?)",
            (film_id, start_time, hall, price),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError as err:
        logging.error("Ошибка добавления сеанса: %s", err)
        return False
    finally:
        conn.close()


def delete_session(session_id):
    """Удаляет сеанс вместе с его билетами (ON DELETE вручную)."""
    conn = get_connection()
    conn.execute("DELETE FROM tickets WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------
# Билеты и бронирование (основной сценарий, ЛР 7-8, 16-17)
# ---------------------------------------------------------------

def get_taken_seats(session_id):
    """Возвращает список занятых мест сеанса: [(ряд, место), ...]."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT row_num, seat_num FROM tickets "
        "WHERE session_id = ? AND status = 'booked'",
        (session_id,),
    ).fetchall()
    conn.close()
    return rows


def _seat_is_taken(conn, session_id, row_num, seat_num):
    """Проверяет, занято ли конкретное место на сеансе (ЛР 22).

    Вынесено из book_ticket, чтобы функция бронирования осталась
    простой и читаемой (рефакторинг ЛР 32).
    """
    row = conn.execute(
        "SELECT id FROM tickets WHERE session_id = ? AND row_num = ? "
        "AND seat_num = ? AND status = 'booked'",
        (session_id, row_num, seat_num),
    ).fetchone()
    return row is not None


def book_ticket(session_id, user_id, row_num, seat_num):
    """Бронирует место на сеанс. Возвращает (True, id) или (False, текст ошибки).

    Перед вставкой проверяет, что место свободно — защита от
    покупки уже занятого места (альтернативный поток сценария).
    """
    conn = get_connection()
    try:
        # 1. Сеанс должен существовать: иначе бронировать некуда
        session = conn.execute(
            "SELECT price FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if session is None:
            return False, "Сеанс не найден"
        # 2. Место должно попадать в схему зала 5 x 10
        if not 1 <= row_num <= HALL_ROWS or not 1 <= seat_num <= HALL_SEATS:
            return False, "Место не существует в этом зале"
        # 3. Место не должно быть занято другой действующей бронью
        if _seat_is_taken(conn, session_id, row_num, seat_num):
            return False, "Место уже занято"
        cursor = conn.execute(
            "INSERT INTO tickets (session_id, user_id, row_num, seat_num, price, "
            "status, booked_at) VALUES (?, ?, ?, ?, ?, 'booked', datetime('now', 'localtime'))",
            (session_id, user_id, row_num, seat_num, session[0]),
        )
        conn.commit()
        return True, cursor.lastrowid
    except sqlite3.IntegrityError as err:
        logging.error("Ошибка бронирования: %s", err)
        return False, "Место уже занято"
    finally:
        conn.close()


def cancel_ticket(ticket_id, user_id=None, is_admin=False):
    """Отменяет бронь: только владелец билета или администратор."""
    conn = get_connection()
    try:
        if is_admin:
            cursor = conn.execute(
                "UPDATE tickets SET status = 'canceled' WHERE id = ?", (ticket_id,)
            )
        else:
            cursor = conn.execute(
                "UPDATE tickets SET status = 'canceled' "
                "WHERE id = ? AND user_id = ?",
                (ticket_id, user_id),
            )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as err:
        logging.error("Ошибка отмены билета: %s", err)
        return False
    finally:
        conn.close()


def get_user_tickets(user_id):
    """Возвращает билеты пользователя с данными фильма и сеанса."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT t.id, t.row_num, t.seat_num, t.price, t.status, t.booked_at, "
        "s.start_time, s.hall, f.title "
        "FROM tickets t JOIN sessions s ON t.session_id = s.id "
        "JOIN films f ON s.film_id = f.id "
        "WHERE t.user_id = ? ORDER BY s.start_time",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def get_all_tickets():
    """Отчёт администратора: все билеты с клиентами (ЛР 6, Use Case №5)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT t.id, u.fio, f.title, s.start_time, s.hall, "
        "t.row_num, t.seat_num, t.price, t.status "
        "FROM tickets t JOIN users u ON t.user_id = u.id "
        "JOIN sessions s ON t.session_id = s.id "
        "JOIN films f ON s.film_id = f.id ORDER BY s.start_time, t.id"
    ).fetchall()
    conn.close()
    return rows


def get_stats():
    """Сводка для панели администратора: количества и выручка."""
    conn = get_connection()
    stats = {}
    stats["films"] = conn.execute("SELECT COUNT(*) FROM films").fetchone()[0]
    stats["sessions"] = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    stats["tickets"] = conn.execute(
        "SELECT COUNT(*) FROM tickets WHERE status = 'booked'"
    ).fetchone()[0]
    stats["revenue"] = conn.execute(
        "SELECT COALESCE(SUM(price), 0) FROM tickets WHERE status = 'booked'"
    ).fetchone()[0]
    conn.close()
    return stats
