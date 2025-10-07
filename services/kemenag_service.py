import sqlite3

DB_NAME = "sindi.db"

def _conn():
    return sqlite3.connect(DB_NAME)

def get_pengajuan_pending():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT id, nama_santri, nis, tanggal, nomor_ijazah, status FROM pengajuan WHERE status='Diajukan' ORDER BY id ASC")
        return c.fetchall()

def verify_pengajuan(pengajuan_id):
    try:
        pid = int(pengajuan_id)
    except:
        return False
    with _conn() as conn:
        c = conn.cursor()
        c.execute("UPDATE pengajuan SET status='Diverifikasi' WHERE id=?", (pid,))
        conn.commit()
    return True
