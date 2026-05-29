import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "surveillance.db"


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                fullname TEXT NOT NULL,
                email TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                niveau TEXT NOT NULL,
                message TEXT NOT NULL,
                classes TEXT,
                photo_path TEXT,
                video_path TEXT,
                status TEXT NOT NULL DEFAULT 'non_lu'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cameras (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                source TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                last_connection TEXT
            )
            """
        )
        seed_default_users(conn)
        seed_default_camera(conn)


def seed_default_users(conn: sqlite3.Connection) -> None:
    users = [
        (
            1,
            "superviseur",
            hash_password("admin123"),
            "superviseur",
            "Admin Superviseur",
            "admin@surveillance.local",
        ),
        (
            2,
            "technicien",
            hash_password("tech123"),
            "technicien",
            "Jean Technicien",
            "tech@surveillance.local",
        ),
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO users
        (id, username, password, role, fullname, email)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        users,
    )


def seed_default_camera(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO cameras
        (id, name, source, type, status, last_connection)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (1, "Camera principale", "0", "webcam", "active", datetime.now().isoformat()),
    )


def authenticate_user(username: str, password: str) -> dict | None:
    if not username or not password:
        return None

    with get_connection() as conn:
        user = conn.execute(
            """
            SELECT id, username, role, fullname, email
            FROM users
            WHERE username = ? AND password = ?
            """,
            (username.strip(), hash_password(password)),
        ).fetchone()
    return dict(user) if user else None


def save_alert(alerte: dict, classes: list[str] | list[int], photo_path=None, video_path=None) -> int:
    class_text = ", ".join(str(item) for item in classes) if classes else ""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO alerts (timestamp, niveau, message, classes, photo_path, video_path, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                alerte.get("niveau", "INFO"),
                alerte.get("message", ""),
                class_text,
                str(photo_path) if photo_path else None,
                str(video_path) if video_path else None,
                "non_lu",
            ),
        )
        return int(cursor.lastrowid)


def get_dashboard_stats() -> dict:
    today = datetime.now().date().isoformat()
    photos_dir = BASE_DIR / "evidences" / "photos"
    photos_count = len(list(photos_dir.glob("*.*"))) if photos_dir.exists() else 0

    with get_connection() as conn:
        alerts_today = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE timestamp LIKE ?",
            (f"{today}%",),
        ).fetchone()[0]
        unread = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE status = 'non_lu'"
        ).fetchone()[0]
        total_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        active_cameras = conn.execute(
            "SELECT COUNT(*) FROM cameras WHERE status = 'active'"
        ).fetchone()[0]

    return {
        "alerts_today": alerts_today,
        "unread": unread,
        "total_alerts": total_alerts,
        "active_cameras": active_cameras,
        "evidences": photos_count,
    }


def get_alerts(niveau="Tous", status="Tous", date_value=None, limit: int | None = None) -> list[dict]:
    conditions = []
    params = []

    if niveau and niveau != "Tous":
        conditions.append("niveau = ?")
        params.append(niveau)
    if status and status != "Tous":
        conditions.append("status = ?")
        params.append(status)
    if date_value:
        conditions.append("timestamp LIKE ?")
        params.append(f"{date_value}%")

    query = "SELECT * FROM alerts"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY timestamp DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def update_alert_status(alert_id: int, status: str) -> str:
    with get_connection() as conn:
        conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (status, alert_id))
    return "Statut mis a jour."


def get_cameras() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM cameras ORDER BY id").fetchall()
    return [dict(row) for row in rows]
