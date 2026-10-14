# Login app (Flask + SQLite)

Frontend (plain HTML/CSS/JS in `public/`) and backend share one SQLite database (`app.db`, created on first run from `schema.sql`).

## Run
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # http://localhost:3000
```

## Structure
- `schema.sql` – tables: `users`, `notes`
- `db.py` – SQLite connection per request, and `init_db()` which applies the schema
- `app.py` – API: `/api/register`, `/api/login`, `/api/logout`, `/api/me`, `/api/notes`
- `public/` – login/register screen and a signed-in page that reads/writes notes

## Configuration
- `SECRET_KEY` – signs session cookies. If unset, one is generated once and saved to `.secret_key` (don't commit that file).
- `FLASK_ENV=production` – turns off debug mode and marks cookies Secure (needs HTTPS).
- `PORT` – default 3000.

## Security notes
- Passwords are hashed with Werkzeug (scrypt, salted); never stored in plain text.
- Sessions are signed cookies: HttpOnly, SameSite=Lax, cleared and reissued on login.
- Failed logins are throttled per IP+email (in memory, resets on restart).
- Before going live: use HTTPS, run behind a production server such as `gunicorn app:app` instead of `python app.py`, and add CSRF protection if you allow cross-site requests.
