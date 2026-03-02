# FocusLog

#### Description

FocusLog is a web application I built to bring structure to self-directed studying. I originally designed it for tracking curricula like CS50, The Odin Project, or OSSU, where students navigate weeks, lectures, and problem sets, and a simple to-do list isn’t sufficient to track effort over time.

The app is built with Flask, SQLite, and Bootstrap. The core concept is a hierarchical data structure:

- **Course** – The high-level container (e.g., “CS50x 2025”).
- **Module** – A unit within a course (e.g., “Week 1 – C”).
- **Task** – A concrete work item (e.g., “PSET1: Mario Less”).
- **Session** – A block of time spent on a task, recording the date, duration, and notes.

You define the curriculum structure once, optionally set target hours and/or a number of weeks and hours per week, and then log sessions as I study. The summary page provides a visualization of whether you are hitting your planned targets.

---

## Features

### User Management

- **Authentication:** Users can register, log in, and log out.
- **Security:** Passwords are hashed using `werkzeug.security` before storing.
- **Data Scoping:** All data (courses, sessions, etc.) is scoped to the logged-in user via `user_id`.

### Curriculum Tracking

- **Dynamic Targets:** I implemented a JavaScript helper on the course creation form to keep targets in sync. If I input "Total Hours" and "Weeks," the "Hours Per Week" is calculated automatically in the browser.
- **Progress:** Courses, modules, and tasks can be marked as complete.
- **Flexibility:** Users can edit or delete courses, which cascades down to remove associated modules and tasks.

### Session Logging

- **The Logger:** You can log a session against any task by choosing the date, start time, and end time.
- **Calculation:** The backend calculates `duration_minutes` automatically based on the time inputs.
- **Review:** You can view a history of sessions or edit them if you made a mistake.

### The Dashboard

The **Summary** page acts as the main hub:

- **Aggregates:** Shows total time logged and total sessions at a glance.
- **Course Overview:** A table displaying the status of each course.
- **Visuals:** I used custom CSS and a small JavaScript snippet to animate progress bars that fill up based on the percentage of `actual_hours` vs `target_hours`.

---

## Database Design

I chose a relational schema to handle the nested nature of the data.

- `users`: Stores `id` and hashed `password`.
- `courses`: Linked to `users`. Stores target metrics (`target_total_hours`, `target_weeks`) and completion status.
- `modules`: Linked to `courses`. Includes an `order_index` to keep weeks sorted correctly.
- `tasks`: Linked to `modules`. Distinguishes between different tasks under a certain module.
- `sessions`: Linked to both `users` and `tasks`.

**Design Choice: Time Storage**
I debated how to store the session time. I decided to store `start_time` and `end_time` for the historical record, but I also calculate and store `duration_minutes` as an integer in the database. This allows the Summary page to sum total hours via a simple SQL query (`SUM(duration_minutes)`) without needing to recalculate time deltas for every single session on every page load.

## If I had more time

If I were to spend more time on this project I would:

- Implement a feature to reorder courses, modules, and tasks.
- Come up with a better design for the tasks ie the problem sets should ideally be under a PSET 'folder'.

---

## File Overview

- `app.py`
  The main Flask controller. Configures the app, database connections, and defines all routes (Auth, CRUD, Dashboard). It includes helper functions like `get_course_or_404` to enforce permission checking (ensuring users can't edit courses they don't own).

- `schema.sql`
  The SQL file that creates the five core tables and establishes relationships between the tables.

- `focuslog.db`
  The SQLite database.

- `helpers.py`
  Contains the `login_required` decorator used to secure routes.

- `templates/`

  - `layout.html`: Base template with Navbar and Bootstrap links.
  - `summary.html`: The dashboard view with progress bars.
  - `auth/`: Login and Register forms.
  - `courses/`, `modules/`, `tasks/`, `sessions/`: Contains the `list`, `detail`, and `form` templates for each entity.

- `static/styles.css`
  Custom CSS overrides (specifically card styling and badge colors).

- `static/main.js`
  Handles the client-side logic for the target calculator and progress bar animations.

---

## AI Assistance

I utilized AI tools (ChatGPT) during development to assist with specific implementation details, such as the JavaScript for auto-calculating target fields and the CSS for animating progress bars. I also used it to brainstorm the initial database structure and some of the more complex SQL commands. All generated code was reviewed, tested, and adapted by me.
