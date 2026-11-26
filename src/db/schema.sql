-- ============================================================
-- Схема базы данных онлайн-кинотеатра «Космос» (ЛР 14)
-- СУБД: SQLite 3. Файл БД: src/db/project.db
-- Таблицы построены по классам из аналитической диаграммы (ЛР 9):
--   Пользователь -> users, Фильм -> films,
--   КиноСеанс -> sessions, Билет -> tickets
-- ============================================================

-- Пользователи системы: клиенты и администраторы (ЛР 19)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    fio TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'client'
);

-- Фильмы репертуара кинотеатра
CREATE TABLE IF NOT EXISTS films (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    genre TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    age_rating TEXT NOT NULL,
    description TEXT
);

-- Киносеансы: показ фильма в зале в указанное время
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    film_id INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    hall TEXT NOT NULL,
    price REAL NOT NULL,
    FOREIGN KEY (film_id) REFERENCES films(id)
);

-- Билеты: место в зале на конкретный сеанс (уникальность места)
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    row_num INTEGER NOT NULL,
    seat_num INTEGER NOT NULL,
    price REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'booked',
    booked_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE (session_id, row_num, seat_num)
);

-- Индекс для быстрого поиска занятых мест сеанса
CREATE INDEX IF NOT EXISTS idx_tickets_session
    ON tickets (session_id, status);
