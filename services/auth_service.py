from flask import session, redirect, url_for, flash
import sqlite3
from functools import wraps

DB_NAME = "sindi.db"

def login_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, username, password, role, kode_mdt, wilayah FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[2] == password:
        session["user"] = {
            "id": row[0], "username": row[1], "role": row[3], "kode_mdt": row[4], "wilayah": row[5]
        }
        return True
    return False

def logout_user():
    session.clear()

def current_user():
    return session.get("user")

def require_role(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Silakan login.", "warning")
                return redirect(url_for("login"))
            if roles and user["role"] not in roles:
                flash("Akses ditolak.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return deco
