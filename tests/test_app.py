"""Автотесты веб-интерфейса (ЛР 28-29): страницы, роли, сценарии."""
import src.backend.db as db


def _login(client, login="admin", password="admin123"):
    """Вспомогательная функция входа через форму."""
    return client.post("/login", data={"login": login, "password": password},
                       follow_redirects=True)


def _setup_session(client):
    """Создаёт фильм и сеанс, возвращает id сеанса."""
    db.add_film("Тестовый фильм", "фантастика", 100, "12+")
    film_id = db.get_films()[0][0]
    db.add_session(film_id, "2026-12-01 12:00", "Зал 1", 300)
    return db.get_sessions()[0][0]


def test_index_page_shows_films(client):
    """На главной отображается афиша с фильмами."""
    db.add_film("Открытие", "драма", 120, "16+")
    response = client.get("/")
    assert response.status_code == 200
    assert "Открытие".encode() in response.data


def test_login_admin_success(client):
    """Вход администратора: появляется ссылка на админ-панель."""
    response = _login(client, "admin", "admin123")
    assert response.status_code == 200
    assert "Админ-панель".encode() in response.data


def test_login_wrong_password(client):
    """Негативный тест: неверный пароль — сообщение об ошибке."""
    response = _login(client, "admin", "badpass")
    assert "Неверный логин или пароль".encode() in response.data


def test_register_new_client(client):
    """Регистрация нового клиента через форму."""
    response = client.post(
        "/register",
        data={"fio": "Тестов Тест", "login": "newuser", "password": "1234"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert db.find_user_by_login("newuser") is not None


def test_register_empty_fields_rejected(client):
    """Негативный тест: пустые поля не пропускаются (ЛР 16, валидация)."""
    response = client.post("/register", data={"fio": "", "login": "", "password": ""})
    assert response.status_code == 400
    assert "Заполните все поля".encode() in response.data


def test_admin_pages_require_role(client):
    """Клиент (и гость) не видит админ-страницы — получаете 403 (ЛР 19)."""
    db.add_user("plain", "1234", "Простой Клиент")
    _login(client, "plain", "1234")
    response = client.get("/admin")
    assert response.status_code == 403
    assert "Доступ запрещён".encode() in response.data


def test_admin_panel_for_admin(client):
    """Администратор видит панель со статистикой."""
    _login(client, "admin", "admin123")
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Админ-панель".encode() in response.data


def test_session_page_seat_map(client):
    """На странице сеанса отображается схема зала 5x10."""
    session_id = _setup_session(client)
    response = client.get(f"/session/{session_id}")
    assert response.status_code == 200
    # 50 кнопок-мест = 10 мест x 5 рядов
    assert response.data.count(b'type="submit"') == 50


def test_booking_requires_login(client):
    """Гость не может забронировать место — перенаправляется на вход."""
    session_id = _setup_session(client)
    response = client.post(
        "/book",
        data={"session_id": session_id, "row_seat": "1:1"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_booking_flow_end_to_end(client):
    """Сквозной сценарий: вход -> бронирование -> билет в «Мои билеты»."""
    _login(client, "admin", "admin123")
    session_id = _setup_session(client)
    response = client.post(
        "/book",
        data={"session_id": session_id, "row_seat": "2:5"},
        follow_redirects=True,
    )
    assert "Билет".encode() in response.data
    my_page = client.get("/my")
    assert "Тестовый фильм".encode() in my_page.data


def test_double_booking_shows_error(client):
    """Повторное бронирование того же места показывает понятное сообщение."""
    db.add_user("client1", "1234", "Клиент Один")
    _login(client, "client1", "1234")
    session_id = _setup_session(client)
    client.post("/book", data={"session_id": session_id, "row_seat": "3:3"})
    response = client.post(
        "/book", data={"session_id": session_id, "row_seat": "3:3"},
        follow_redirects=True,
    )
    assert "Место уже занято".encode() in response.data


def test_404_page(client):
    """Несуществующая страница и сеанс отдают страницу 404."""
    response = client.get("/session/9999")
    assert response.status_code == 404
    assert "Страница не найдена".encode() in response.data


# ---------------------------------------------------------------
# Тесты исправленных дефектов (ЛР 29, 31-32)
# ---------------------------------------------------------------

def test_login_ignores_external_redirect(client):
    """BUG-001: параметр next с чужим адресом не используется для перехода."""
    response = client.post(
        "/login?next=//example.com",
        data={"login": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_register_short_password_rejected(client):
    """BUG-002: слишком короткий пароль не принимается формой регистрации."""
    response = client.post(
        "/register", data={"fio": "Тестов Тест", "login": "short", "password": "123"}
    )
    assert response.status_code == 400
    assert "не менее 4 символов".encode() in response.data


def test_admin_add_film(client):
    """Администратор добавляет фильм через форму — фильм появляется в афише."""
    _login(client, "admin", "admin123")
    response = client.post(
        "/admin/films/add",
        data={"title": "Новый фильм", "genre": "драма", "duration": 95,
              "age_rating": "12+", "description": "Описание"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Новый фильм".encode() in response.data


def test_admin_add_film_empty_form(client):
    """Пустая форма добавления фильма возвращает 400 и сообщение об ошибке."""
    _login(client, "admin", "admin123")
    response = client.post("/admin/films/add", data={"title": "", "genre": ""})
    assert response.status_code == 400
    assert "Заполните все обязательные поля".encode() in response.data


def test_admin_edit_film(client):
    """Администратор редактирует фильм — изменения сохраняются в БД."""
    _login(client, "admin", "admin123")
    db.add_film("Старое имя", "драма", 100, "12+")
    film_id = db.get_films()[0][0]
    response = client.post(
        f"/admin/films/{film_id}/edit",
        data={"title": "Новое имя", "genre": "боевик", "duration": 110,
              "age_rating": "16+", "description": "Новое описание"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert db.get_film(film_id)[1] == "Новое имя"


def test_admin_add_session_negative_price_rejected(client):
    """BUG-003: сеанс с отрицательной ценой не создаётся."""
    _login(client, "admin", "admin123")
    db.add_film("Фильм", "драма", 100, "12+")
    film_id = db.get_films()[0][0]
    response = client.post(
        "/admin/sessions/add",
        data={"film_id": film_id, "start_time": "2026-12-05 12:00",
              "hall": "Зал 1", "price": -100},
    )
    assert response.status_code == 400
    assert "цена должна быть больше нуля".encode() in response.data


def test_admin_session_add_and_delete(client):
    """Администратор добавляет и удаляет сеанс; удаление убирает сеанс из БД."""
    _login(client, "admin", "admin123")
    db.add_film("Фильм", "драма", 100, "12+")
    film_id = db.get_films()[0][0]
    client.post(
        "/admin/sessions/add",
        data={"film_id": film_id, "start_time": "2026-12-05 12:00",
              "hall": "Зал 1", "price": 250},
        follow_redirects=True,
    )
    sessions = db.get_sessions()
    assert len(sessions) == 1
    response = client.post(f"/admin/sessions/{sessions[0][0]}/delete",
                           follow_redirects=True)
    assert response.status_code == 200
    assert db.get_sessions() == []


def test_cancel_foreign_ticket_shows_message(client):
    """Попытка отменить чужой билет показывает понятное сообщение."""
    db.add_user("owner", "1234", "Владелец Билета")
    db.add_user("other", "1234", "Другой Клиент")
    owner_id = db.find_user_by_login("owner")[0]
    session_id = _setup_session(client)
    ok, ticket_id = db.book_ticket(session_id, owner_id, 1, 1)
    assert ok
    _login(client, "other", "1234")
    response = client.post(f"/ticket/{ticket_id}/cancel", follow_redirects=True)
    assert "Не удалось отменить бронь".encode() in response.data


def test_logout_clears_session(client):
    """Выход из системы очищает сессию и возвращает на афишу."""
    _login(client, "admin", "admin123")
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert "Вход".encode() in response.data


def test_admin_tickets_report(client):
    """Отчёт о продажах доступен администратору и содержит таблицу билетов."""
    _login(client, "admin", "admin123")
    session_id = _setup_session(client)
    film_id = db.get_films()[0][0]
    assert film_id
    db.book_ticket(session_id, 1, 2, 2)
    response = client.get("/admin/tickets")
    assert response.status_code == 200
    assert "Отчёт о продажах".encode() in response.data


def test_my_tickets_requires_login(client):
    """Страница «Мои билеты» без входа перенаправляет на форму входа."""
    response = client.get("/my", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
