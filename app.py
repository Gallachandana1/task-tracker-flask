from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# ---------------- APP ----------------
app = Flask(__name__)
app.secret_key = "change_this_to_a_long_random_key"
DB = "tasks.db"

# ---------------- DATABASE INIT ----------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        deadline TEXT,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

# ---------------- HELPERS ----------------
def get_db():
    return sqlite3.connect(DB)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

# ---------------- AUTO MARK MISSED ----------------
def auto_mark_missed():
    today = date.today().isoformat()
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        UPDATE tasks
        SET status = 'missed'
        WHERE status = 'pending' AND deadline < ?
    """, (today,))

    conn.commit()
    conn.close()

# ---------------- HOME ----------------
@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
@login_required
def dashboard():
    auto_mark_missed()

    conn = get_db()
    c = conn.cursor()

    # Get tasks
    c.execute("""
        SELECT id, title, deadline, status
        FROM tasks
        WHERE user_id = ?
    """, (session["user_id"],))
    tasks = c.fetchall()

    # Get stats
    c.execute("""
        SELECT status, COUNT(*)
        FROM tasks
        WHERE user_id = ?
        GROUP BY status
    """, (session["user_id"],))
    raw_stats = c.fetchall()

    conn.close()

    stats = {"pending": 0, "completed": 0, "missed": 0}
    for status, count in raw_stats:
        stats[status] = count

    return render_template(
        "dashboard.html",
        username=session["username"],
        tasks=tasks,
        stats=stats
    )

# ---------------- ADD TASK ----------------
@app.route("/add", methods=["POST"])
@login_required
def add_task():
    title = request.form["task"]
    deadline = request.form["deadline"]

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tasks (user_id, title, deadline)
        VALUES (?, ?, ?)
    """, (session["user_id"], title, deadline))

    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ---------------- RECOVER ----------------
@app.route("/recover/<int:task_id>")
@login_required
def recover(task_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='pending' WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# --------------- COMPLETE ----------------
@app.route("/complete/<int:task_id>")
@login_required
def complete(task_id):
    conn = get_db()
    c = conn.cursor()

    c.execute(
        "UPDATE tasks SET status='completed' WHERE id=? AND user_id=?",
        (task_id, session["user_id"])
    )

    conn.commit()
    conn.close()
    return redirect("/dashboard")


# ---------------- DELETE ----------------
@app.route("/delete/<int:task_id>")
@login_required
def delete(task_id):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "DELETE FROM tasks WHERE id=? AND user_id=?",
        (task_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    return redirect("/dashboard")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, password FROM users WHERE username=?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            return redirect("/dashboard")

        return "Invalid credentials"

    return render_template("login.html")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return "Username already exists"
        finally:
            conn.close()

        return redirect("/login")

    return render_template("register.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- RUN ----------------
init_db()
if __name__ == "__main__":
    app.run()
