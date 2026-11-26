"""Веб-приложение «Онлайн-кинотеатр „Космос"» (Flask).

Реализует сценарии из ЛР 6-8:
  клиент — афиша, выбор сеанса и мест, бронирование, мои билеты;
  администратор — управление афишей, сеансами, отчёт по билетам.
Авторизация и роли — ЛР 19, обработка ошибок и логирование — ЛР 20.
"""
import functools
import logging

from flask import (Flask, flash, redirect, render_template, request,
                   session, url_for)

import src.backend.db as db

# Логирование сбоев в файл app.log (ЛР 20, задание 2)
logging.basicConfig(
    filename="app.log", level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s"
)

app = Flask(
    __name__,
    template_folder="../frontend/templates",
    static_folder="../frontend/static",
)
app.secret_key = "kosmos-cinema-up2026"  # ключ сессий (учебный проект)

# Роли пользователей (ЛР 19): вынесены в константы, чтобы не дублировать строки
ROLE_ADMIN = "admin"
ROLE_CLIENT = "client"


# ---------------------------------------------------------------
# Вспомогательные функции разбора форм (рефакторинг ЛР 26, 32)
# ---------------------------------------------------------------

def _read_film_form(form):
    """Читает и проверяет поля формы фильма (ЛР 16-17).

    :return: словарь с данными или None, если обязательные поля пусты
    """
    data = {
        "title": form.get("title", "").strip(),
        "genre": form.get("genre", "").strip(),
        "duration": form.get("duration", type=int),
        "age": form.get("age_rating", "").strip(),
        "description": form.get("description", "").strip(),
    }
    if not data["title"] or not data["genre"] or not data["duration"] or not data["age"]:
        return None
    return data


def _parse_row_seat(value):
    """Разбирает значение кнопки-места «ряд:место» в два числа (ЛР 22).

    :return: (ряд, место) или (None, None), если формат неверный
    """
    if ":" not in value:
        return None, None
    try:
        row_num, seat_num = (int(part) for part in value.split(":"))
    except ValueError:
        return None, None
    return row_num, seat_num


def _read_session_form(form):
    """Читает и проверяет поля формы сеанса (ЛР 16-17).

    Цена обязательна и должна быть больше нуля (BUG-003).

    :return: словарь с данными или None при ошибке валидации
    """
    data = {
        "film_id": form.get("film_id", type=int),
        "start_time": form.get("start_time", "").strip(),
        "hall": form.get("hall", "").strip(),
        "price": form.get("price", type=float),
    }
    if not data["film_id"] or not data["start_time"] or not data["hall"]:
        return None
    if data["price"] is None or data["price"] <= 0:
        return None
    return data


def _read_register_form(form):
    """Читает и проверяет поля формы регистрации (ЛР 19, 26).

    :return: (данные, None) при успехе или (None, текст ошибки)
    """
    data = {
        "login": form.get("login", "").strip(),
        "password": form.get("password", ""),
        "fio": form.get("fio", "").strip(),
    }
    if not data["login"] or not data["password"] or not data["fio"]:
        return None, "Заполните все поля формы"
    if len(data["password"]) < 4:
        return None, "Пароль должен содержать не менее 4 символов"
    return data, None


def _safe_next_url(value):
    """Возвращает локальный адрес перехода или None (BUG-001: open redirect).

    Адрес «//example.com» браузер понимает как чужой сайт, поэтому
    такой вариант отклоняем.
    """
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return None


# ---------------------------------------------------------------
# Декораторы ограничения доступа (ЛР 19, задание 2)
# ---------------------------------------------------------------

def login_required(view):
    """Декоратор: переход на страницу только для вошедших пользователей."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Войдите в систему, чтобы продолжить", "error")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Декоратор: страница доступна только роли admin. Иначе — 403."""

    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))
        if session.get("role") != ROLE_ADMIN:
            return render_template("403.html"), 403
        return view(*args, **kwargs)

    return wrapped


# ---------------------------------------------------------------
# Публичные страницы
# ---------------------------------------------------------------

@app.route("/")
def index():
    """Главная страница — афиша фильмов с ближайшими сеансами (Use Case №1)."""
    films = db.get_films()
    sessions = db.get_sessions()
    # собираем для каждого фильма список его сеансов
    films_with_sessions = []
    for film in films:
        film_sessions = [s for s in sessions if s[4] == film[1]]
        films_with_sessions.append({"film": film, "sessions": film_sessions})
    return render_template("index.html", items=films_with_sessions)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Регистрация нового клиента (вспомогательный Use Case)."""
    if request.method == "POST":
        data, error = _read_register_form(request.form)
        if error:
            flash(error, "error")
            return render_template("register.html"), 400
        if db.find_user_by_login(data["login"]):
            flash("Логин уже занят", "error")
            return render_template("register.html"), 400
        if db.add_user(data["login"], data["password"], data["fio"], ROLE_CLIENT):
            flash("Регистрация прошла успешно, войдите в систему", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Вход в систему: логин + пароль, роль сохраняется в сессии (ЛР 19)."""
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        password = request.form.get("password", "")
        user = db.check_login(login, password)
        if user is None:
            flash("Неверный логин или пароль", "error")
            return render_template("login.html"), 401
        session["user_id"], session["role"] = user
        session["login"] = login
        flash("Вы вошли в систему", "success")
        next_url = _safe_next_url(request.args.get("next")
                                  or request.form.get("next"))
        if next_url:
            return redirect(next_url)
        return redirect(url_for("index"))
    return render_template("login.html", next=request.args.get("next", ""))


@app.route("/logout")
def logout():
    """Выход из системы."""
    session.clear()
    flash("Вы вышли из системы", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------
# Бронирование билетов (основной сценарий клиента, ЛР 7-8)
# ---------------------------------------------------------------

@app.route("/session/<int:session_id>")
def session_page(session_id):
    """Страница сеанса: схема зала с занятыми и свободными местами."""
    film_session = db.get_session(session_id)
    if film_session is None:
        return render_template("404.html"), 404
    taken = db.get_taken_seats(session_id)
    taken_set = {(row, seat) for row, seat in taken}
    # схема зала: 5 рядов по 10 мест
    hall = []
    for row_num in range(1, db.HALL_ROWS + 1):
        row = []
        for seat_num in range(1, db.HALL_SEATS + 1):
            row.append({"num": seat_num, "taken": (row_num, seat_num) in taken_set})
        hall.append({"num": row_num, "seats": row})
    return render_template("session.html", s=film_session, hall=hall)


@app.route("/book", methods=["POST"])
@login_required
def book():
    """Бронирование выбранного места (Use Case «Забронировать место»).

    Кнопка-место передаёт значение в формате «ряд:место».
    """
    session_id = request.form.get("session_id", type=int)
    row_num, seat_num = _parse_row_seat(request.form.get("row_seat", ""))
    if session_id is None or row_num is None:
        flash("Не выбрано место для бронирования", "error")
        return redirect(url_for("index"))
    ok, result = db.book_ticket(session_id, session["user_id"], row_num, seat_num)
    if ok:
        flash(f"Билет №{result} оформлен: ряд {row_num}, место {seat_num}", "success")
    else:
        flash(result, "error")  # например, «Место уже занято»
    return redirect(url_for("session_page", session_id=session_id))


@app.route("/my")
@login_required
def my_tickets():
    """Личные билеты пользователя («Мои билеты»)."""
    tickets = db.get_user_tickets(session["user_id"])
    return render_template("my_tickets.html", tickets=tickets)


@app.route("/ticket/<int:ticket_id>/cancel", methods=["POST"])
@login_required
def cancel(ticket_id):
    """Отмена брони: клиент — только свои билеты, админ — любые."""
    is_admin = session.get("role") == ROLE_ADMIN
    user_id = None if is_admin else session["user_id"]
    if db.cancel_ticket(ticket_id, user_id, is_admin):
        flash("Бронь отменена", "success")
    else:
        flash("Не удалось отменить бронь: билет не найден "
              "или принадлежит другому пользователю", "error")
    return redirect(request.referrer or url_for("my_tickets"))


# ---------------------------------------------------------------
# Панель администратора (роли и разграничение, ЛР 19)
# ---------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_panel():
    """Панель администратора: сводка по фильмотеке и продажам."""
    stats = db.get_stats()
    return render_template("admin.html", stats=stats)


@app.route("/admin/films")
@admin_required
def admin_films():
    """Список фильмов с кнопками редактирования и удаления."""
    films = db.get_films()
    return render_template("admin_films.html", films=films)


@app.route("/admin/films/add", methods=["GET", "POST"])
@admin_required
def admin_film_add():
    """Форма добавления фильма в афишу (Use Case «Добавить фильм»)."""
    if request.method == "POST":
        data = _read_film_form(request.form)
        if data is None:
            flash("Заполните все обязательные поля", "error")
            return render_template("film_form.html"), 400
        if db.add_film(data["title"], data["genre"], data["duration"],
                       data["age"], data["description"]):
            flash(f"Фильм «{data['title']}» добавлен в афишу", "success")
            return redirect(url_for("admin_films"))
        flash("Не удалось сохранить фильм, попробуйте позже", "error")
    return render_template("film_form.html")


@app.route("/admin/films/<int:film_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_film_edit(film_id):
    """Форма редактирования фильма (операция Update, ЛР 17)."""
    film = db.get_film(film_id)
    if film is None:
        return render_template("404.html"), 404
    if request.method == "POST":
        data = _read_film_form(request.form)
        if data is None:
            flash("Заполните все обязательные поля", "error")
            return render_template("film_form.html", film=film), 400
        db.update_film(film_id, data["title"], data["genre"], data["duration"],
                       data["age"], data["description"])
        flash("Изменения сохранены", "success")
        return redirect(url_for("admin_films"))
    return render_template("film_form.html", film=film)


@app.route("/admin/films/<int:film_id>/delete", methods=["POST"])
@admin_required
def admin_film_delete(film_id):
    """Удаление фильма (операция Delete, ЛР 17, обработка ошибок связей)."""
    if db.delete_film(film_id):
        flash("Фильм удалён", "success")
    else:
        flash("Нельзя удалить фильм: у него есть сеансы в расписании", "error")
    return redirect(url_for("admin_films"))


@app.route("/admin/sessions")
@admin_required
def admin_sessions():
    """Расписание всех сеансов."""
    sessions = db.get_sessions()
    return render_template("admin_sessions.html", sessions=sessions)


@app.route("/admin/sessions/add", methods=["GET", "POST"])
@admin_required
def admin_session_add():
    """Форма добавления сеанса в расписание."""
    films = db.get_films()
    if request.method == "POST":
        data = _read_session_form(request.form)
        if data is None:
            flash("Заполните все поля формы: цена должна быть больше нуля", "error")
            return render_template("session_form.html", films=films), 400
        if db.add_session(data["film_id"], data["start_time"],
                          data["hall"], data["price"]):
            flash("Сеанс добавлен в расписание", "success")
            return redirect(url_for("admin_sessions"))
        flash("Не удалось сохранить сеанс", "error")
    return render_template("session_form.html", films=films)


@app.route("/admin/sessions/<int:session_id>/delete", methods=["POST"])
@admin_required
def admin_session_delete(session_id):
    """Удаление сеанса вместе с его билетами."""
    db.delete_session(session_id)
    flash("Сеанс удалён вместе с его билетами", "success")
    return redirect(url_for("admin_sessions"))


@app.route("/admin/tickets")
@admin_required
def admin_tickets():
    """Отчёт о продажах билетов (Use Case «Просмотреть отчёт»)."""
    tickets = db.get_all_tickets()
    stats = db.get_stats()
    return render_template("admin_tickets.html", tickets=tickets, stats=stats)


# ---------------------------------------------------------------
# Обработчики ошибок: пользователь видит понятную страницу,
# разработчик — запись в app.log (ЛР 20)
# ---------------------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):
    """Страница «Не найдено» вместо стандартной трассировки."""
    return render_template("404.html"), 404


@app.errorhandler(403)
def forbidden(error):
    """Страница «Доступ запрещён» (негативный тест-кейс ролей)."""
    return render_template("403.html"), 403


@app.errorhandler(500)
def server_error(error):
    """Глобальный обработчик: страница «Что-то пошло не так» (ЛР 20, шаг 3)."""
    logging.error("Ошибка сервера: %s", error)
    return render_template("500.html"), 500
