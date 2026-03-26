"""
SQLite database — sessions, sales, activity logs, and users.
"""
import sqlite3, os, hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'cafe.db')

def get_conn(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(path=DB_PATH):
    conn = get_conn(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pcs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            ip TEXT,
            port INTEGER DEFAULT 9000
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pc_name TEXT NOT NULL,
            username TEXT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            total_seconds INTEGER DEFAULT 0,
            coins_inserted INTEGER DEFAULT 0,
            amount_earned REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pc_name TEXT NOT NULL,
            event_type TEXT NOT NULL,
            detail TEXT,
            timestamp TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            saved_seconds INTEGER DEFAULT 0,
            saved_on_pc TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            last_login TEXT
        );
    """)
    # Migrate: add username column to sessions if it doesn't exist yet
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
    if "username" not in cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN username TEXT")
    conn.commit()
    conn.close()

# ── helpers ──────────────────────────────────────────────────
def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

# ── users ────────────────────────────────────────────────────
def register_user(username: str, password: str, path=DB_PATH) -> tuple[bool, str]:
    """Returns (success, message)."""
    conn = get_conn(path)
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
            (username, _hash(password), datetime.now().isoformat())
        )
        conn.commit()
        return True, "Registered successfully."
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

def login_user(username: str, password: str, path=DB_PATH) -> tuple[bool, dict | None]:
    """Returns (success, user_row_dict or None)."""
    conn = get_conn(path)
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username, _hash(password))
    ).fetchone()
    if row:
        conn.execute("UPDATE users SET last_login=? WHERE username=?",
                     (datetime.now().isoformat(), username))
        conn.commit()
        conn.close()
        return True, dict(row)
    conn.close()
    return False, None

def save_user_time(username: str, seconds: int, pc_name: str, path=DB_PATH):
    """Save remaining time for a user and record which PC it was saved on."""
    conn = get_conn(path)
    conn.execute(
        "UPDATE users SET saved_seconds=?, saved_on_pc=? WHERE username=?",
        (seconds, pc_name, username)
    )
    conn.commit()
    conn.close()

def consume_user_time(username: str, pc_name: str, path=DB_PATH) -> int:
    """
    Returns saved seconds for the user and clears them.
    If saved on a different PC, that PC's record is also cleared (anti-abuse).
    """
    conn = get_conn(path)
    row = conn.execute("SELECT saved_seconds, saved_on_pc FROM users WHERE username=?",
                       (username,)).fetchone()
    if not row:
        conn.close()
        return 0
    seconds = row["saved_seconds"]
    conn.execute("UPDATE users SET saved_seconds=0, saved_on_pc='' WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return seconds

def get_user(username: str, path=DB_PATH) -> dict | None:
    conn = get_conn(path)
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

# ── sessions ─────────────────────────────────────────────────
def log_activity(pc_name: str, event_type: str, detail: str = "", path=DB_PATH):
    conn = get_conn(path)
    conn.execute(
        "INSERT INTO activity_log (pc_name, event_type, detail, timestamp) VALUES (?,?,?,?)",
        (pc_name, event_type, detail, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def start_session(pc_name: str, username: str = "", path=DB_PATH) -> int:
    conn = get_conn(path)
    cur = conn.execute(
        "INSERT INTO sessions (pc_name, username, started_at) VALUES (?,?,?)",
        (pc_name, username, datetime.now().isoformat())
    )
    sid = cur.lastrowid
    conn.commit()
    conn.close()
    return sid

def end_session(session_id: int, total_seconds: int, coins: int, amount: float, path=DB_PATH):
    conn = get_conn(path)
    conn.execute(
        "UPDATE sessions SET ended_at=?, total_seconds=?, coins_inserted=?, amount_earned=? WHERE id=?",
        (datetime.now().isoformat(), total_seconds, coins, amount, session_id)
    )
    conn.commit()
    conn.close()

def get_sales_summary(path=DB_PATH) -> list:
    conn = get_conn(path)
    rows = conn.execute("""
        SELECT pc_name,
               strftime('%Y-%m-%d', started_at) as day,
               strftime('%Y-%m', started_at) as month,
               SUM(amount_earned) as total,
               COUNT(*) as sessions
        FROM sessions GROUP BY pc_name, day ORDER BY day DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_activity_logs(pc_name: str = None, limit: int = 200, path=DB_PATH) -> list:
    conn = get_conn(path)
    if pc_name:
        rows = conn.execute(
            "SELECT * FROM activity_log WHERE pc_name=? ORDER BY timestamp DESC LIMIT ?",
            (pc_name, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM activity_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_coin_logs(pc_name: str = None, limit: int = 200, path=DB_PATH) -> list:
    conn = get_conn(path)
    if pc_name:
        rows = conn.execute(
            "SELECT * FROM activity_log WHERE pc_name=? AND event_type='COIN_INSERTED' ORDER BY timestamp DESC LIMIT ?",
            (pc_name, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM activity_log WHERE event_type='COIN_INSERTED' ORDER BY timestamp DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pcs(path=DB_PATH) -> list:
    conn = get_conn(path)
    rows = conn.execute("SELECT * FROM pcs ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def upsert_pc(name: str, ip: str, port: int = 9000, path=DB_PATH):
    conn = get_conn(path)
    conn.execute(
        "INSERT INTO pcs (name,ip,port) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET ip=excluded.ip,port=excluded.port",
        (name, ip, port))
    conn.commit()
    conn.close()

def delete_pc(name: str, path=DB_PATH):
    conn = get_conn(path)
    conn.execute("DELETE FROM pcs WHERE name=?", (name,))
    conn.commit()
    conn.close()
