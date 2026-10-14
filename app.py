import os
import re
import secrets
import sqlite3
import time
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, init_db

BASE_DIR = Path(__file__).parent
IS_PROD = os.environ.get("FLASK_ENV") == "production"


def load_secret_key():
    """Use SECRET_KEY if set; otherwise create one once and keep it in .secret_key
    so logins survive restarts."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    key_file = BASE_DIR / ".secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
    return key_file.read_text().strip()


app = Flask(__name__, static_folder="public", static_url_path="")
app.config.update(
    SECRET_KEY=load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=IS_PROD,  # requires HTTPS in production
    PERMANENT_SESSION_LIFETIME=7 * 24 * 60 * 60,
    MAX_CONTENT_LENGTH=10 * 1024,
)
app.teardown_appcontext(close_db)
init_db()

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# Compared against when an email isn't registered, so timing doesn't reveal which emails exist.
DUMMY_HASH = generate_password_hash("not-a-real-password")

# Very small in-memory login throttle: 8 failures per 15 minutes per IP+email.
attempts = {}
WINDOW = 15 * 60
MAX_FAILS = 8


def throttled(key):
    now = time.time()
    attempts[key] = [t for t in attempts.get(key, []) if now - t < WINDOW]
    return len(attempts[key]) >= MAX_FAILS


def record_failure(key):
    attempts.setdefault(key, []).append(time.time())


def body():
    return request.get_json(silent=True) or {}


def public_user(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"], "createdAt": row["created_at"]}


def start_session(user_id):
    session.clear()  # drop any old session data (prevents session fixation)
    session["user_id"] = user_id
    session.permanent = True


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Please log in first."), 401
        return view(*args, **kwargs)

    return wrapped


# ---------- pages ----------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------- auth ----------
@app.post("/api/register")
def register():
    data = body()
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    if not name:
        return jsonify(error="Enter your name."), 400
    if not EMAIL_RE.match(email):
        return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8:
        return jsonify(error="Use a password with at least 8 characters."), 400

    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify(error="An account with this email already exists."), 409

    start_session(cur.lastrowid)
    user = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(user=public_user(user)), 201


@app.post("/api/login")
def login():
    data = body()
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")
    key = f"{request.remote_addr}|{email}"

    if throttled(key):
        return jsonify(error="Too many attempts. Try again in 15 minutes."), 429

    user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    pw_hash = user["password_hash"] if user else DUMMY_HASH
    ok = check_password_hash(pw_hash, password) and user is not None

    if not ok:
        record_failure(key)
        return jsonify(error="Email or password is incorrect."), 401

    attempts.pop(key, None)
    start_session(user["id"])
    return jsonify(user=public_user(user))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def me():
    user_id = session.get("user_id")
    if user_id is None:
        return jsonify(user=None)
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return jsonify(user=public_user(user) if user else None)


# ---------- notes (example of frontend <-> database data) ----------
@app.get("/api/notes")
@login_required
def list_notes():
    rows = get_db().execute(
        "SELECT id, body, created_at AS createdAt FROM notes WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],),
    ).fetchall()
    return jsonify(notes=[dict(r) for r in rows])


@app.post("/api/notes")
@login_required
def add_note():
    text = str(body().get("body") or "").strip()
    if not text:
        return jsonify(error="Write something before saving."), 400
    if len(text) > 500:
        return jsonify(error="Notes can be up to 500 characters."), 400

    db = get_db()
    cur = db.execute("INSERT INTO notes (user_id, body) VALUES (?, ?)", (session["user_id"], text))
    db.commit()
    note = db.execute(
        "SELECT id, body, created_at AS createdAt FROM notes WHERE id = ?", (cur.lastrowid,)
    ).fetchone()
    return jsonify(note=dict(note)), 201


@app.delete("/api/notes/<int:note_id>")
@login_required
def delete_note(note_id):
    db = get_db()
    cur = db.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, session["user_id"]))
    db.commit()
    if cur.rowcount == 0:
        return jsonify(error="Note not found."), 404
    return jsonify(ok=True)


@app.errorhandler(413)
def too_large(_e):
    return jsonify(error="That request is too large."), 413


if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 3000)), debug=not IS_PROD)
