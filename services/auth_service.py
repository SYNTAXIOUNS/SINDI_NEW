from flask import session, redirect, url_for, flash
import sqlite3
from functools import wraps

DB_NAME = "sindi.db"

# ==========================
# 🔐 LOGIN SYSTEM
# ==========================

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, password, role, kode_mdt, wilayah FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()

    # Sementara tanpa hash, cek langsung
    if row and row[2] == password:
        session["user"] = {
            "id": row[0],
            "username": row[1],
            "role": row[3],
            "kode_mdt": row[4],
            "wilayah": row[5],
        }
        return True
    return False


def logout_user():
    session.clear()


def current_user():
    return session.get("user")


# ==========================
# 🛡️ ROLE-BASED ACCESS CONTROL
# ==========================

def require_role(roles):
    """
    Decorator untuk membatasi akses berdasarkan role pengguna.
    Contoh:
        @require_role("kanwil")
        @require_role(["kanwil", "admin"])
    """
    # pastikan roles bisa berupa list
    if isinstance(roles, str):
        roles = [roles]

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash("⚠️ Anda harus login terlebih dahulu.", "warning")
                return redirect(url_for("login"))

            if user["role"] not in roles:
                flash("⛔ Akses ditolak: Anda tidak memiliki izin untuk halaman ini.", "danger")
                return redirect(url_for("dashboard"))

            return fn(*args, **kwargs)
        return wrapper
    return decorator
