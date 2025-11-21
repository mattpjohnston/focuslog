-- users table
CREATE TABLE users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash     TEXT NOT NULL
);

-- courses table
CREATE TABLE courses (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id              INTEGER NOT NULL,
    name                 TEXT NOT NULL,
    description          TEXT,
    target_total_hours   REAL,
    target_weeks         INTEGER,
    target_hours_per_week REAL,
    completed            INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- modules table
CREATE TABLE modules (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id    INTEGER NOT NULL,
    name         TEXT NOT NULL,
    order_index  INTEGER NOT NULL DEFAULT 1,
    target_hours REAL,
    completed    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

-- tasks table
CREATE TABLE tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id    INTEGER NOT NULL,
    name         TEXT NOT NULL,
    type         TEXT,
    order_index  INTEGER NOT NULL DEFAULT 1,
    target_hours REAL,
    completed    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (module_id) REFERENCES modules(id)
);

-- sessions table
CREATE TABLE sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          INTEGER NOT NULL,
    task_id          INTEGER NOT NULL,
    date             TEXT NOT NULL,
    start_time       TEXT NOT NULL,
    end_time         TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    notes            TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);