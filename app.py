import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    abort,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-change-me")
app.config["DATABASE"] = os.path.join(app.root_path, "focuslog.db")


# Database helpers


def get_db():
    """Get a SQLite connection for the current request."""
    if "db" not in g:
        db_path = app.config["DATABASE"]
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    """Close the DB connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# Helper functions to get owned rows


def get_course_or_404(course_id):
    """Get a course that belongs to the user, or 404."""
    user_id = session.get("user_id")
    db = get_db()
    cur = db.execute(
        "SELECT * FROM courses WHERE id = ? AND user_id = ?",
        (course_id, user_id),
    )
    course = cur.fetchone()
    if course is None:
        abort(404)
    return course


def get_module_or_404(module_id):
    """Get a module whose course belongs to the user, or 404."""
    user_id = session.get("user_id")
    db = get_db()
    cur = db.execute(
        """
        SELECT m.*, c.name AS course_name
        FROM modules m
        JOIN courses c ON m.course_id = c.id
        WHERE m.id = ? AND c.user_id = ?
        """,
        (module_id, user_id),
    )
    module = cur.fetchone()
    if module is None:
        abort(404)
    return module


def get_task_or_404(task_id):
    """Get a task whose course belongs to the user, or 404."""
    user_id = session.get("user_id")
    db = get_db()
    cur = db.execute(
        """
        SELECT t.*,
               m.name AS module_name,
               m.id   AS module_id,
               c.name AS course_name,
               c.id   AS course_id
        FROM tasks t
        JOIN modules m ON t.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        WHERE t.id = ? AND c.user_id = ?
        """,
        (task_id, user_id),
    )
    task = cur.fetchone()
    if task is None:
        abort(404)
    return task


# Index / summary


@app.route("/")
def index():
    """Redirect based on login state."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("summary"))


@app.route("/summary")
@login_required
def summary():
    """Simple dashboard summary for the current user."""
    user_id = session["user_id"]
    db = get_db()

    # Overall totals
    cur = db.execute(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS total_minutes,
               COUNT(*) AS session_count
        FROM sessions
        WHERE user_id = ?;
        """,
        (user_id,),
    )
    totals = cur.fetchone()

    # Totals per course
    cur = db.execute(
        """
        SELECT c.id,
               c.name,
               c.completed,
               c.target_total_hours,
               c.target_weeks,
               c.target_hours_per_week,
               COALESCE(SUM(s.duration_minutes), 0) AS total_minutes
        FROM courses c
        LEFT JOIN modules m ON m.course_id = c.id
        LEFT JOIN tasks   t ON t.module_id = m.id
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.name;
        """,
        (user_id, user_id),
    )
    courses = cur.fetchall()

    return render_template("summary.html", totals=totals, courses=courses)


# Authentication


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user."""
    if request.method == "GET":
        return render_template("auth/register.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    confirmation = request.form.get("confirmation", "")

    if not username or not password or not confirmation:
        return render_template(
            "auth/register.html",
            error="Please fill in all fields.",
        )

    if password != confirmation:
        return render_template(
            "auth/register.html",
            error="Passwords do not match.",
        )

    db = get_db()
    hash_ = generate_password_hash(password)

    try:
        cur = db.execute(
            "INSERT INTO users (username, hash) VALUES (?, ?)",
            (username, hash_),
        )
        db.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return render_template(
            "auth/register.html",
            error="That username is already taken.",
        )

    session["user_id"] = user_id
    return redirect(url_for("summary"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log a user in."""
    session.clear()

    if request.method == "GET":
        return render_template("auth/login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return render_template(
            "auth/login.html",
            error="Please enter username and password.",
        )

    db = get_db()
    cur = db.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,),
    )
    row = cur.fetchone()

    if row is None or not check_password_hash(row["hash"], password):
        return render_template(
            "auth/login.html",
            error="Invalid username or password.",
        )

    session["user_id"] = row["id"]
    return redirect(url_for("summary"))


@app.route("/logout")
def logout():
    """Log the current user out."""
    session.clear()
    return redirect(url_for("login"))


@app.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change password for the user."""
    if request.method == "GET":
        return render_template("auth/change_password.html")

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirmation = request.form.get("confirmation", "")

    if not current_password or not new_password or not confirmation:
        return render_template(
            "auth/change_password.html",
            error="Please fill in all fields.",
        )

    if new_password != confirmation:
        return render_template(
            "auth/change_password.html",
            error="New passwords do not match.",
        )

    db = get_db()
    user_id = session["user_id"]
    cur = db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()

    if row is None or not check_password_hash(row["hash"], current_password):
        return render_template(
            "auth/change_password.html",
            error="Current password is incorrect.",
        )

    new_hash = generate_password_hash(new_password)
    db.execute(
        "UPDATE users SET hash = ? WHERE id = ?",
        (new_hash, user_id),
    )
    db.commit()

    return redirect(url_for("summary"))


# Courses


@app.route("/courses")
@login_required
def courses():
    """List all courses for the user."""
    user_id = session["user_id"]
    db = get_db()

    cur = db.execute(
        """
        SELECT c.id,
               c.name,
               c.description,
               c.completed,
               c.target_total_hours,
               c.target_weeks,
               c.target_hours_per_week,
               COALESCE(SUM(s.duration_minutes), 0) AS total_minutes
        FROM courses c
        LEFT JOIN modules m ON m.course_id = c.id
        LEFT JOIN tasks   t ON t.module_id = m.id
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.name;
        """,
        (user_id, user_id),
    )
    rows = cur.fetchall()

    return render_template("courses/list.html", courses=rows)


@app.route("/courses/new", methods=["GET", "POST"])
@login_required
def course_new():
    """Create a new course."""
    if request.method == "GET":
        return render_template("courses/form.html", course=None)

    user_id = session["user_id"]
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    total_hours_raw = request.form.get("target_total_hours", "").strip()
    weeks_raw = request.form.get("target_weeks", "").strip()
    per_week_raw = request.form.get("target_hours_per_week", "").strip()

    if not name:
        return render_template(
            "courses/form.html",
            course=None,
            error="Course name is required.",
        )

    def parse_float(value):
        return float(value) if value else None

    def parse_int(value):
        return int(value) if value else None

    try:
        target_total_hours = parse_float(total_hours_raw)
        target_weeks = parse_int(weeks_raw)
        target_hours_per_week = parse_float(per_week_raw)
    except ValueError:
        return render_template(
            "courses/form.html",
            course=None,
            error="Targets must be numeric.",
        )

    db = get_db()
    db.execute(
        """
        INSERT INTO courses
            (user_id, name, description,
             target_total_hours, target_weeks, target_hours_per_week)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            name,
            description,
            target_total_hours,
            target_weeks,
            target_hours_per_week,
        ),
    )
    db.commit()

    return redirect(url_for("courses"))


@app.route("/courses/<int:course_id>")
@login_required
def course_detail(course_id):
    """Show a course, its targets, modules, and progress."""
    course = get_course_or_404(course_id)
    user_id = session["user_id"]
    db = get_db()

    # Lifetime total minutes for this course
    cur = db.execute(
        """
        SELECT COALESCE(SUM(s.duration_minutes), 0) AS total_minutes
        FROM modules m
        LEFT JOIN tasks t ON t.module_id = m.id
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
        WHERE m.course_id = ?;
        """,
        (user_id, course_id),
    )
    course_minutes = cur.fetchone()["total_minutes"]

    # This week's minutes for this course
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    end_of_week = start_of_week + timedelta(days=6)
    start_str = start_of_week.isoformat()
    end_str = end_of_week.isoformat()

    cur = db.execute(
        """
        SELECT COALESCE(SUM(s.duration_minutes), 0) AS weekly_minutes
        FROM modules m
        LEFT JOIN tasks t ON t.module_id = m.id
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
         AND s.date >= ?
         AND s.date <= ?
        WHERE m.course_id = ?;
        """,
        (user_id, start_str, end_str, course_id),
    )
    weekly_minutes = cur.fetchone()["weekly_minutes"]

    # Modules with totals
    cur = db.execute(
        """
        SELECT m.id,
               m.name,
               m.order_index,
               m.completed,
               m.target_hours,
               COALESCE(SUM(s.duration_minutes), 0) AS total_minutes
        FROM modules m
        LEFT JOIN tasks t ON t.module_id = m.id
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
        WHERE m.course_id = ?
        GROUP BY m.id
        ORDER BY m.order_index;
        """,
        (user_id, course_id),
    )
    modules = cur.fetchall()

    return render_template(
        "courses/detail.html",
        course=course,
        course_minutes=course_minutes,
        weekly_minutes=weekly_minutes,
        modules=modules,
        start_of_week=start_of_week,
        end_of_week=end_of_week,
    )


@app.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
def course_edit(course_id):
    """Edit a course's name/description/targets."""
    course = get_course_or_404(course_id)
    db = get_db()

    if request.method == "GET":
        return render_template("courses/form.html", course=course)

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    total_hours_raw = request.form.get("target_total_hours", "").strip()
    weeks_raw = request.form.get("target_weeks", "").strip()
    per_week_raw = request.form.get("target_hours_per_week", "").strip()

    if not name:
        return render_template(
            "courses/form.html",
            course=course,
            error="Course name is required.",
        )

    def parse_float(value):
        return float(value) if value else None

    def parse_int(value):
        return int(value) if value else None

    try:
        target_total_hours = parse_float(total_hours_raw)
        target_weeks = parse_int(weeks_raw)
        target_hours_per_week = parse_float(per_week_raw)
    except ValueError:
        return render_template(
            "courses/form.html",
            course=course,
            error="Targets must be numeric.",
        )

    db.execute(
        """
        UPDATE courses
           SET name = ?,
               description = ?,
               target_total_hours = ?,
               target_weeks = ?,
               target_hours_per_week = ?
         WHERE id = ?;
        """,
        (
            name,
            description,
            target_total_hours,
            target_weeks,
            target_hours_per_week,
            course_id,
        ),
    )
    db.commit()

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/toggle-complete", methods=["POST"])
@login_required
def course_toggle_complete(course_id):
    """Toggle completion status for a course."""
    course = get_course_or_404(course_id)
    db = get_db()
    new_value = 0 if course["completed"] else 1
    db.execute(
        "UPDATE courses SET completed = ? WHERE id = ?",
        (new_value, course_id),
    )
    db.commit()
    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/courses/<int:course_id>/delete", methods=["POST"])
@login_required
def course_delete(course_id):
    """Delete a course and everything under it (modules, tasks, sessions)."""
    get_course_or_404(course_id)
    user_id = session["user_id"]
    db = get_db()

    # Delete sessions for tasks under this course
    db.execute(
        """
        DELETE FROM sessions
        WHERE user_id = ?
          AND task_id IN (
              SELECT t.id
              FROM tasks t
              JOIN modules m ON t.module_id = m.id
              WHERE m.course_id = ?
          );
        """,
        (user_id, course_id),
    )

    # Delete tasks
    db.execute(
        """
        DELETE FROM tasks
        WHERE module_id IN (
            SELECT m.id FROM modules m WHERE m.course_id = ?
        );
        """,
        (course_id,),
    )

    # Delete modules
    db.execute(
        "DELETE FROM modules WHERE course_id = ?;",
        (course_id,),
    )

    # Delete course
    db.execute(
        "DELETE FROM courses WHERE id = ? AND user_id = ?;",
        (course_id, user_id),
    )
    db.commit()

    return redirect(url_for("courses"))


# Modules


@app.route("/courses/<int:course_id>/modules/new", methods=["GET", "POST"])
@login_required
def module_new(course_id):
    """Create a new module under a course."""
    course = get_course_or_404(course_id)
    db = get_db()

    if request.method == "GET":
        return render_template("modules/form.html", course=course, module=None)

    name = request.form.get("name", "").strip()
    target_hours_raw = request.form.get("target_hours", "").strip()

    if not name:
        return render_template(
            "modules/form.html",
            course=course,
            module=None,
            error="Module name is required.",
        )

    target_hours = None
    if target_hours_raw:
        try:
            target_hours = float(target_hours_raw)
        except ValueError:
            return render_template(
                "modules/form.html",
                course=course,
                module=None,
                error="Target hours must be a number.",
            )

    cur = db.execute(
        "SELECT COALESCE(MAX(order_index), 0) AS max_idx FROM modules WHERE course_id = ?",
        (course_id,),
    )
    max_idx = cur.fetchone()["max_idx"]
    next_index = max_idx + 1

    db.execute(
        """
        INSERT INTO modules (course_id, name, order_index, target_hours)
        VALUES (?, ?, ?, ?)
        """,
        (course_id, name, next_index, target_hours),
    )
    db.commit()

    return redirect(url_for("course_detail", course_id=course_id))


@app.route("/modules/<int:module_id>")
@login_required
def module_detail(module_id):
    """Show a module with its tasks."""
    module = get_module_or_404(module_id)
    user_id = session["user_id"]
    db = get_db()

    # Lifetime total minutes for this module
    cur = db.execute(
        """
        SELECT COALESCE(SUM(s.duration_minutes), 0) AS total_minutes
        FROM tasks t
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
        WHERE t.module_id = ?;
        """,
        (user_id, module_id),
    )
    module_minutes = cur.fetchone()["total_minutes"]

    # This week's minutes
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_str = start_of_week.isoformat()
    end_str = end_of_week.isoformat()

    cur = db.execute(
        """
        SELECT COALESCE(SUM(s.duration_minutes), 0) AS weekly_minutes
        FROM tasks t
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
         AND s.date >= ?
         AND s.date <= ?
        WHERE t.module_id = ?;
        """,
        (user_id, start_str, end_str, module_id),
    )
    weekly_minutes = cur.fetchone()["weekly_minutes"]

    # Tasks
    cur = db.execute(
        """
        SELECT t.id,
               t.name,
               t.type,
               t.order_index,
               t.completed,
               t.target_hours,
               COALESCE(SUM(s.duration_minutes), 0) AS total_minutes
        FROM tasks t
        LEFT JOIN sessions s
          ON s.task_id = t.id
         AND s.user_id = ?
        WHERE t.module_id = ?
        GROUP BY t.id
        ORDER BY t.order_index;
        """,
        (user_id, module_id),
    )
    tasks = cur.fetchall()

    return render_template(
        "modules/detail.html",
        module=module,
        module_minutes=module_minutes,
        weekly_minutes=weekly_minutes,
        tasks=tasks,
        start_of_week=start_of_week,
        end_of_week=end_of_week,
    )


@app.route("/modules/<int:module_id>/edit", methods=["GET", "POST"])
@login_required
def module_edit(module_id):
    """Edit a module."""
    module = get_module_or_404(module_id)
    db = get_db()

    if request.method == "GET":
        # Need the course for the form heading
        course = get_course_or_404(module["course_id"])
        return render_template("modules/form.html", course=course, module=module)

    name = request.form.get("name", "").strip()
    target_hours_raw = request.form.get("target_hours", "").strip()

    if not name:
        course = get_course_or_404(module["course_id"])
        return render_template(
            "modules/form.html",
            course=course,
            module=module,
            error="Module name is required.",
        )

    target_hours = None
    if target_hours_raw:
        try:
            target_hours = float(target_hours_raw)
        except ValueError:
            course = get_course_or_404(module["course_id"])
            return render_template(
                "modules/form.html",
                course=course,
                module=module,
                error="Target hours must be a number.",
            )

    db.execute(
        """
        UPDATE modules
           SET name = ?,
               target_hours = ?
         WHERE id = ?;
        """,
        (name, target_hours, module_id),
    )
    db.commit()

    return redirect(url_for("module_detail", module_id=module_id))


@app.route("/modules/<int:module_id>/toggle-complete", methods=["POST"])
@login_required
def module_toggle_complete(module_id):
    """Toggle completion for a module."""
    module = get_module_or_404(module_id)
    db = get_db()
    new_value = 0 if module["completed"] else 1
    db.execute(
        "UPDATE modules SET completed = ? WHERE id = ?",
        (new_value, module_id),
    )
    db.commit()
    return redirect(url_for("module_detail", module_id=module_id))


@app.route("/modules/<int:module_id>/delete", methods=["POST"])
@login_required
def module_delete(module_id):
    """Delete a module and everything under it (tasks + sessions)."""
    module = get_module_or_404(module_id)
    user_id = session["user_id"]
    db = get_db()

    # Delete sessions for tasks in this module
    db.execute(
        """
        DELETE FROM sessions
        WHERE user_id = ?
          AND task_id IN (
              SELECT t.id FROM tasks t WHERE t.module_id = ?
          );
        """,
        (user_id, module_id),
    )

    # Delete tasks
    db.execute("DELETE FROM tasks WHERE module_id = ?;", (module_id,))

    # Delete the module itself
    db.execute("DELETE FROM modules WHERE id = ?;", (module_id,))
    db.commit()

    return redirect(url_for("course_detail", course_id=module["course_id"]))


# Tasks


@app.route("/modules/<int:module_id>/tasks/new", methods=["GET", "POST"])
@login_required
def task_new(module_id):
    """Create a new task under a module."""
    module = get_module_or_404(module_id)
    db = get_db()

    if request.method == "GET":
        return render_template("tasks/form.html", module=module, task=None)

    name = request.form.get("name", "").strip()
    type_ = request.form.get("type", "").strip() or None
    target_hours_raw = request.form.get("target_hours", "").strip()

    if not name:
        return render_template(
            "tasks/form.html",
            module=module,
            task=None,
            error="Task name is required.",
        )

    target_hours = None
    if target_hours_raw:
        try:
            target_hours = float(target_hours_raw)
        except ValueError:
            return render_template(
                "tasks/form.html",
                module=module,
                task=None,
                error="Target hours must be a number.",
            )

    cur = db.execute(
        "SELECT COALESCE(MAX(order_index), 0) AS max_idx FROM tasks WHERE module_id = ?",
        (module_id,),
    )
    max_idx = cur.fetchone()["max_idx"]
    next_index = max_idx + 1

    db.execute(
        """
        INSERT INTO tasks (module_id, name, type, order_index, target_hours)
        VALUES (?, ?, ?, ?, ?)
        """,
        (module_id, name, type_, next_index, target_hours),
    )
    db.commit()

    return redirect(url_for("module_detail", module_id=module_id))


@app.route("/tasks/<int:task_id>")
@login_required
def task_detail(task_id):
    """Show a single task and its sessions."""
    task = get_task_or_404(task_id)
    user_id = session["user_id"]
    db = get_db()

    # Lifetime total
    cur = db.execute(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS total_minutes
        FROM sessions
        WHERE task_id = ? AND user_id = ?;
        """,
        (task_id, user_id),
    )
    task_minutes = cur.fetchone()["total_minutes"]

    # This week
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    start_str = start_of_week.isoformat()
    end_str = end_of_week.isoformat()

    cur = db.execute(
        """
        SELECT COALESCE(SUM(duration_minutes), 0) AS weekly_minutes
        FROM sessions
        WHERE task_id = ? AND user_id = ?
          AND date >= ? AND date <= ?;
        """,
        (task_id, user_id, start_str, end_str),
    )
    weekly_minutes = cur.fetchone()["weekly_minutes"]

    # Sessions for this task
    cur = db.execute(
        """
        SELECT *
        FROM sessions
        WHERE task_id = ? AND user_id = ?
        ORDER BY date DESC, start_time DESC;
        """,
        (task_id, user_id),
    )
    sessions_rows = cur.fetchall()

    return render_template(
        "tasks/detail.html",
        task=task,
        task_minutes=task_minutes,
        weekly_minutes=weekly_minutes,
        sessions=sessions_rows,
        start_of_week=start_of_week,
        end_of_week=end_of_week,
    )


@app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
@login_required
def task_edit(task_id):
    """Edit a task."""
    task = get_task_or_404(task_id)
    module = get_module_or_404(task["module_id"])
    db = get_db()

    if request.method == "GET":
        return render_template("tasks/form.html", module=module, task=task)

    name = request.form.get("name", "").strip()
    type_ = request.form.get("type", "").strip() or None
    target_hours_raw = request.form.get("target_hours", "").strip()

    if not name:
        return render_template(
            "tasks/form.html",
            module=module,
            task=task,
            error="Task name is required.",
        )

    target_hours = None
    if target_hours_raw:
        try:
            target_hours = float(target_hours_raw)
        except ValueError:
            return render_template(
                "tasks/form.html",
                module=module,
                task=task,
                error="Target hours must be a number.",
            )

    db.execute(
        """
        UPDATE tasks
           SET name = ?,
               type = ?,
               target_hours = ?
         WHERE id = ?;
        """,
        (name, type_, target_hours, task_id),
    )
    db.commit()

    return redirect(url_for("task_detail", task_id=task_id))


@app.route("/tasks/<int:task_id>/toggle-complete", methods=["POST"])
@login_required
def task_toggle_complete(task_id):
    """Toggle completion for a task."""
    task = get_task_or_404(task_id)
    db = get_db()
    new_value = 0 if task["completed"] else 1
    db.execute(
        "UPDATE tasks SET completed = ? WHERE id = ?",
        (new_value, task_id),
    )
    db.commit()
    return redirect(url_for("task_detail", task_id=task_id))


@app.route("/tasks/<int:task_id>/delete", methods=["POST"])
@login_required
def task_delete(task_id):
    """Delete a task and its sessions."""
    task = get_task_or_404(task_id)
    user_id = session["user_id"]
    db = get_db()

    # Delete sessions
    db.execute(
        "DELETE FROM sessions WHERE task_id = ? AND user_id = ?;",
        (task_id, user_id),
    )

    # Delete task
    db.execute("DELETE FROM tasks WHERE id = ?;", (task_id,))
    db.commit()

    return redirect(url_for("module_detail", module_id=task["module_id"]))


# Sessions


@app.route("/sessions")
@login_required
def sessions_view():
    """List recent sessions for the current user."""
    user_id = session["user_id"]
    db = get_db()

    cur = db.execute(
        """
        SELECT s.id,
               s.date,
               s.start_time,
               s.end_time,
               s.duration_minutes,
               s.notes,
               t.id   AS task_id,
               t.name AS task_name,
               m.name AS module_name,
               c.name AS course_name
        FROM sessions s
        JOIN tasks   t ON s.task_id = t.id
        JOIN modules m ON t.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        WHERE s.user_id = ?
        ORDER BY s.date DESC, s.start_time DESC
        LIMIT 100;
        """,
        (user_id,),
    )
    rows = cur.fetchall()

    return render_template("sessions/list.html", sessions=rows)


@app.route("/sessions/new", methods=["GET", "POST"])
@login_required
def session_new():
    """Log a new study session."""
    user_id = session["user_id"]
    db = get_db()

    if request.method == "GET":
        # Optional preselected task
        preselected_task_id = request.args.get("task_id", type=int)

        cur = db.execute(
            """
            SELECT t.id,
                   t.name,
                   t.type,
                   m.name AS module_name,
                   c.name AS course_name
            FROM tasks t
            JOIN modules m ON t.module_id = m.id
            JOIN courses c ON m.course_id = c.id
            WHERE c.user_id = ?
            ORDER BY c.name, m.order_index, t.order_index;
            """,
            (user_id,),
        )
        tasks = cur.fetchall()

        error = None
        if not tasks:
            error = "Create a course, module, and task before logging sessions."

        return render_template(
            "sessions/form.html",
            tasks=tasks,
            preselected_task_id=preselected_task_id,
            error=error,
            existing=None,
        )

    # POST
    task_id = request.form.get("task_id", type=int)
    date_str = request.form.get("date", "").strip()
    start_str = request.form.get("start_time", "").strip()
    end_str = request.form.get("end_time", "").strip()
    notes = request.form.get("notes", "").strip() or None

    # Helper to re-render on error
    def render_with_error(msg):
        cur2 = db.execute(
            """
            SELECT t.id,
                   t.name,
                   t.type,
                   m.name AS module_name,
                   c.name AS course_name
            FROM tasks t
            JOIN modules m ON t.module_id = m.id
            JOIN courses c ON m.course_id = c.id
            WHERE c.user_id = ?
            ORDER BY c.name, m.order_index, t.order_index;
            """,
            (user_id,),
        )
        tasks2 = cur2.fetchall()
        return render_template(
            "sessions/form.html",
            tasks=tasks2,
            preselected_task_id=task_id,
            error=msg,
            existing=None,
        )

    if not task_id or not date_str or not start_str or not end_str:
        return render_with_error("Please fill in all required fields.")

    # Ensure task belongs to this user
    _ = get_task_or_404(task_id)

    try:
        start_dt = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{date_str} {end_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return render_with_error("Invalid date or time format.")

    if end_dt <= start_dt:
        return render_with_error("End time must be after start time.")

    duration_minutes = int((end_dt - start_dt).total_seconds() // 60)

    db.execute(
        """
        INSERT INTO sessions
            (user_id, task_id, date, start_time, end_time, duration_minutes, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            task_id,
            date_str,
            start_dt.strftime("%Y-%m-%d %H:%M"),
            end_dt.strftime("%Y-%m-%d %H:%M"),
            duration_minutes,
            notes,
        ),
    )
    db.commit()

    return redirect(url_for("sessions_view"))


@app.route("/sessions/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
def session_edit(session_id):
    """Edit an existing session."""
    user_id = session["user_id"]
    db = get_db()

    cur = db.execute(
        """
        SELECT s.*,
               t.id   AS task_id,
               t.name AS task_name,
               m.name AS module_name,
               c.name AS course_name
        FROM sessions s
        JOIN tasks   t ON s.task_id = t.id
        JOIN modules m ON t.module_id = m.id
        JOIN courses c ON m.course_id = c.id
        WHERE s.id = ? AND s.user_id = ?;
        """,
        (session_id, user_id),
    )
    session_row = cur.fetchone()
    if session_row is None:
        abort(404)

    if request.method == "GET":
        # All tasks
        cur = db.execute(
            """
            SELECT t.id,
                   t.name,
                   t.type,
                   m.name AS module_name,
                   c.name AS course_name
            FROM tasks t
            JOIN modules m ON t.module_id = m.id
            JOIN courses c ON m.course_id = c.id
            WHERE c.user_id = ?
            ORDER BY c.name, m.order_index, t.order_index;
            """,
            (user_id,),
        )
        tasks = cur.fetchall()

        date_str = session_row["date"]
        start_time = session_row["start_time"][11:16]
        end_time = session_row["end_time"][11:16]

        return render_template(
            "sessions/edit.html",
            session_row=session_row,
            tasks=tasks,
            date_str=date_str,
            start_time=start_time,
            end_time=end_time,
        )

    # POST: update
    task_id = request.form.get("task_id", type=int)
    date_str = request.form.get("date", "").strip()
    start_str = request.form.get("start_time", "").strip()
    end_str = request.form.get("end_time", "").strip()
    notes = request.form.get("notes", "").strip() or None

    def render_with_error(msg):
        cur2 = db.execute(
            """
            SELECT t.id,
                   t.name,
                   t.type,
                   m.name AS module_name,
                   c.name AS course_name
            FROM tasks t
            JOIN modules m ON t.module_id = m.id
            JOIN courses c ON m.course_id = c.id
            WHERE c.user_id = ?
            ORDER BY c.name, m.order_index, t.order_index;
            """,
            (user_id,),
        )
        tasks2 = cur2.fetchall()
        return render_template(
            "sessions/edit.html",
            session_row=session_row,
            tasks=tasks2,
            date_str=date_str,
            start_time=start_str,
            end_time=end_str,
            error=msg,
        )

    if not task_id or not date_str or not start_str or not end_str:
        return render_with_error("Please fill in all required fields.")

    _ = get_task_or_404(task_id)

    try:
        start_dt = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{date_str} {end_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return render_with_error("Invalid date or time format.")

    if end_dt <= start_dt:
        return render_with_error("End time must be after start time.")

    duration_minutes = int((end_dt - start_dt).total_seconds() // 60)

    db.execute(
        """
        UPDATE sessions
           SET task_id = ?,
               date = ?,
               start_time = ?,
               end_time = ?,
               duration_minutes = ?,
               notes = ?
         WHERE id = ? AND user_id = ?;
        """,
        (
            task_id,
            date_str,
            start_dt.strftime("%Y-%m-%d %H:%M"),
            end_dt.strftime("%Y-%m-%d %H:%M"),
            duration_minutes,
            notes,
            session_id,
            user_id,
        ),
    )
    db.commit()

    return redirect(url_for("sessions_view"))


@app.route("/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
def session_delete(session_id):
    """Delete a session."""
    user_id = session["user_id"]
    db = get_db()
    db.execute(
        "DELETE FROM sessions WHERE id = ? AND user_id = ?;",
        (session_id, user_id),
    )
    db.commit()
    return redirect(url_for("sessions_view"))


if __name__ == "__main__":
    app.run(debug=True)
