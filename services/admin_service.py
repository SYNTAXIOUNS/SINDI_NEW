import sqlite3

DB_NAME = "sindi.db"

def _conn():
    return sqlite3.connect(DB_NAME)

def list_users():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, role, kode_mdt, wilayah FROM users ORDER BY id DESC")
        return c.fetchall()

def create_user(username, password, role, kode_mdt=None, wilayah=None):
    if role not in ("mdt","kankemenag","kanwil"):
        return False, "Role tidak valid."
    try:
        with _conn() as conn:
            c = conn.cursor()
            c.execute("""INSERT INTO users (username, password, role, kode_mdt, wilayah)
                         VALUES (?, ?, ?, ?, ?)""",
                      (username, password, role, kode_mdt, wilayah))
            conn.commit()
        return True, f"User '{username}' berhasil dibuat."
    except sqlite3.IntegrityError:
        return False, "Username sudah ada."
