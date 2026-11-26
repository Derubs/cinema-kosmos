"""Автотесты модуля работы с БД (ЛР 28, «белый ящик» по функциям db.py)."""
import hashlib

import src.backend.db as db


def test_add_and_find_user(temp_db):
    """Регистрация и поиск пользователя по логину."""
    assert db.add_user("testuser", "1234", "Тестов Тест") is True
    user = db.find_user_by_login("testuser")
    assert user is not None
    assert user[1] == "testuser"
    assert user[3] == "Тестов Тест"
    assert user[4] == "client"


def test_duplicate_login_rejected(temp_db):
    """Повторная регистрация с тем же логином отклоняется."""
    db.add_user("dup", "1234", "Первый")
    assert db.add_user("dup", "5678", "Второй") is False


def test_check_login_correct_and_wrong(temp_db):
    """Вход с верным паролем возвращает (id, role), с неверным — None."""
    db.add_user("admin2", "admin123", "Админ", role="admin")
    assert db.check_login("admin2", "admin123") is not None
    assert db.check_login("admin2", "wrongpass") is None
    # пароль хранится именно хешем, а не открытым текстом
    user = db.find_user_by_login("admin2")
    assert user[2] == hashlib.sha256("admin123".encode()).hexdigest()


def test_film_crud(temp_db):
    """Полный цикл CRUD фильма: добавление, чтение, изменение, удаление."""
    assert db.add_film("Тестовый фильм", "драма", 100, "12+", "Описание")
    films = db.get_films()
    assert len(films) == 1
    film_id = films[0][0]
    db.update_film(film_id, "Новое имя", "боевик", 110, "16+", "Новое описание")
    film = db.get_film(film_id)
    assert film[1] == "Новое имя"
    assert db.delete_film(film_id) is True
    assert db.get_film(film_id) is None


def test_delete_film_with_sessions_blocked(temp_db):
    """Фильм с сеансами удалить нельзя (защита внешних связей, ЛР 17)."""
    db.add_film("Фильм с сеансом", "фантастика", 90, "6+")
    film_id = db.get_films()[0][0]
    db.add_session(film_id, "2026-12-01 10:00", "Зал 1", 200)
    assert db.delete_film(film_id) is False
    assert db.get_film(film_id) is not None


def test_book_ticket_success(temp_db):
    """Успешное бронирование свободного места."""
    db.add_user("client1", "1234", "Клиент Один")
    user_id = db.find_user_by_login("client1")[0]
    db.add_film("Фильм", "комедия", 100, "12+")
    film_id = db.get_films()[0][0]
    db.add_session(film_id, "2026-12-01 12:00", "Зал 1", 300)
    session_id = db.get_sessions()[0][0]
    ok, ticket_id = db.book_ticket(session_id, user_id, 2, 7)
    assert ok is True
    taken = db.get_taken_seats(session_id)
    assert (2, 7) in taken


def test_book_taken_seat_rejected(temp_db):
    """Бронирование занятого места отклоняется (альтернативный поток)."""
    db.add_user("client1", "1234", "Клиент Один")
    user_id = db.find_user_by_login("client1")[0]
    db.add_film("Фильм", "комедия", 100, "12+")
    film_id = db.get_films()[0][0]
    db.add_session(film_id, "2026-12-01 12:00", "Зал 1", 300)
    session_id = db.get_sessions()[0][0]
    db.book_ticket(session_id, user_id, 1, 1)
    ok, message = db.book_ticket(session_id, user_id, 1, 1)
    assert ok is False
    assert "занято" in message.lower()


def test_book_seat_out_of_hall_rejected(temp_db):
    """Место вне схемы зала (ряд 6) не бронируется."""
    db.add_user("client1", "1234", "Клиент Один")
    user_id = db.find_user_by_login("client1")[0]
    db.add_film("Фильм", "комедия", 100, "12+")
    film_id = db.get_films()[0][0]
    db.add_session(film_id, "2026-12-01 12:00", "Зал 1", 300)
    session_id = db.get_sessions()[0][0]
    ok, message = db.book_ticket(session_id, user_id, 6, 1)
    assert ok is False
    assert "не существует" in message


def test_cancel_ticket_only_owner_or_admin(temp_db):
    """Отмена брони: владелец может, чужой пользователь — нет."""
    db.add_user("client1", "1234", "Клиент Один")
    db.add_user("client2", "1234", "Клиент Два")
    id1 = db.find_user_by_login("client1")[0]
    id2 = db.find_user_by_login("client2")[0]
    db.add_film("Фильм", "комедия", 100, "12+")
    film_id = db.get_films()[0][0]
    db.add_session(film_id, "2026-12-01 12:00", "Зал 1", 300)
    session_id = db.get_sessions()[0][0]
    ok, ticket_id = db.book_ticket(session_id, id1, 4, 4)
    # чужой клиент не может отменить
    assert db.cancel_ticket(ticket_id, id2, is_admin=False) is False
    # владелец может отменить
    assert db.cancel_ticket(ticket_id, id1, is_admin=False) is True
    assert db.get_user_tickets(id1)[0][4] == "canceled"


def test_stats_counts(temp_db):
    """Сводка администратора считает фильмы, сеансы, билеты и выручку."""
    db.add_user("client1", "1234", "Клиент Один")
    user_id = db.find_user_by_login("client1")[0]
    db.add_film("Фильм", "комедия", 100, "12+")
    film_id = db.get_films()[0][0]
    db.add_session(film_id, "2026-12-01 12:00", "Зал 1", 300)
    session_id = db.get_sessions()[0][0]
    db.book_ticket(session_id, user_id, 1, 1)
    db.book_ticket(session_id, user_id, 1, 2)
    stats = db.get_stats()
    assert stats["films"] == 1
    assert stats["sessions"] == 1
    assert stats["tickets"] == 2
    assert stats["revenue"] == 600.0
