# services/mdt_service.py
import sqlite3, datetime, os, pandas as pd
from fpdf import FPDF
from flask import send_file

BASE_DIR = "/tmp" if os.getenv("RENDER") else os.getcwd()
HASIL_DIR = os.path.join(BASE_DIR, "hasil_excel")
DB_PATH = os.path.join(BASE_DIR, "sindi.db")
os.makedirs(HASIL_DIR, exist_ok=True)


# ======================
# KONEKSI DATABASE
# ======================
def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ======================
# MIGRASI / INIT
# ======================

def init_db():
    with _conn() as conn:
        c = conn.cursor()
        for col, tipe in [
            ("alasan", "TEXT"),
            ("kabupaten", "TEXT"),
            ("tanggal_verifikasi", "TEXT"),
            ("verifikator", "TEXT"),
            ("file_hasil", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE pengajuan ADD COLUMN {col} {tipe}")
            except sqlite3.OperationalError:
                pass  # kolom sudah ada

        c.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_verifikasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pengajuan_id INTEGER,
            nama_mdt TEXT,
            jenjang TEXT,
            tahun TEXT,
            jumlah_lulus INTEGER,
            status TEXT,
            alasan TEXT,
            verifikator TEXT,
            tanggal_verifikasi TEXT
        )
        """)
        conn.commit()

# ======================
# MDT: PENGAJUAN
# ======================
def create_pengajuan_batch(mdt_user, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, file_lulusan_path):
    nomor_batch = f"BATCH_{mdt_user['kode_mdt']}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    kabupaten = mdt_user.get("wilayah", "-")

    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO pengajuan (
                nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                file_lulusan, tanggal_pengajuan, status, nomor_batch,
                mdt_id, kabupaten
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
            file_lulusan_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Menunggu", nomor_batch, mdt_user["id"], kabupaten
        ))
        conn.commit()
    return nomor_batch


def list_pengajuan_batch_by_mdt(mdt_id):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                   jumlah_lulus, file_lulusan, status, kabupaten
            FROM pengajuan WHERE mdt_id=? ORDER BY id DESC
        """, (mdt_id,))
        return c.fetchall()

# ======================
# KANKEMENAG: VERIFIKASI
# ======================
def list_pengajuan_for_kemenag():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                   file_lulusan, status, kabupaten
            FROM pengajuan WHERE status='Menunggu' ORDER BY id DESC
        """)
        return c.fetchall()

# ======================
# KANWIL: PENETAPAN NOMOR IJAZAH
# ======================
def list_pengajuan_for_kanwil():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                   file_lulusan, status, kabupaten, alasan, verifikator, tanggal_verifikasi
            FROM pengajuan WHERE status='Diverifikasi' ORDER BY id DESC
        """)
        return c.fetchall()


# ===========================================================
# 🔸 Tetapkan Pengajuan oleh Kanwil (Render-safe)
# ===========================================================
def tetapkan_pengajuan(pengajuan_id):
    """Kanwil menetapkan pengajuan dan generate file hasil."""
    conn = _conn()
    c = conn.cursor()

    c.execute("SELECT file_lulusan, nama_mdt, jenjang, tahun_pelajaran FROM pengajuan WHERE id=?", (pengajuan_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise Exception("Data pengajuan tidak ditemukan.")

    file_lulusan, nama_mdt, jenjang, tahun = row

    hasil_file = generate_nomor_ijazah_batch(pengajuan_id)

    c.execute("""
        UPDATE pengajuan
        SET status='Ditetapkan',
            file_hasil=?,
            tanggal_verifikasi=?
        WHERE id=?
    """, (hasil_file, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pengajuan_id))
    conn.commit()
    conn.close()

    print(f"✅ Pengajuan {pengajuan_id} berhasil ditetapkan → {hasil_file}")
    return hasil_file

# ===========================================================
# 🔸 Endpoint helper (untuk unduh di Render)
# ===========================================================
def get_hasil_excel(filename):
    path = os.path.join(HASIL_DIR, filename)
    if not os.path.exists(path):
        return f"<h4 style='color:red'>❌ File tidak ditemukan: {path}</h4>"
    return send_file(path, as_attachment=True)

# ===========================================================
# 🔸 Generate File Hasil Penetapan Ijazah (Aman untuk Render)
# ===========================================================
def tetapkan_pengajuan(pengajuan_id):
    """Kanwil menetapkan pengajuan dan generate file hasil."""
    conn = _conn()
    c = conn.cursor()

    c.execute("SELECT file_lulusan, nama_mdt, jenjang, tahun_pelajaran FROM pengajuan WHERE id=?", (pengajuan_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        raise Exception("Data pengajuan tidak ditemukan.")

    file_lulusan, nama_mdt, jenjang, tahun = row

    hasil_file = generate_nomor_ijazah_batch(pengajuan_id)

    c.execute("""
        UPDATE pengajuan
        SET status='Ditetapkan',
            file_hasil=?,
            tanggal_verifikasi=?
        WHERE id=?
    """, (hasil_file, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pengajuan_id))
    conn.commit()
    conn.close()

    print(f"✅ Pengajuan {pengajuan_id} berhasil ditetapkan → {hasil_file}")
    return hasil_file

# ======================
# MDT & KANWIL: HASIL
# ======================
def get_nomor_ijazah_by_pengajuan(pengajuan_id):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT nama_santri, nis, nomor_ijazah, tahun, jenjang
            FROM nomor_ijazah WHERE pengajuan_id=? ORDER BY id ASC
        """, (pengajuan_id,))
        return c.fetchall()

def list_hasil_penetapan(kode_mdt=None, kabupaten=None, jenjang=None):
    conn = _conn()
    c = conn.cursor()
    query = """
        SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, kabupaten,
               nomor_batch, COALESCE(file_hasil, file_lulusan)
        FROM pengajuan WHERE status='Ditetapkan'
    """
    params = []
    if kode_mdt:
        query += " AND nama_mdt=?"; params.append(kode_mdt)
    if kabupaten:
        query += " AND kabupaten=?"; params.append(kabupaten)
    if jenjang:
        query += " AND jenjang=?"; params.append(jenjang)
    query += " ORDER BY id DESC"

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    hasil = []
    for r in rows:
        file_path = r[7]
        if file_path:
            file_path = os.path.basename(file_path.replace("\\", "/"))
        hasil.append({
            "id": r[0],
            "nama_mdt": r[1],
            "jenjang": r[2],
            "tahun": r[3],
            "jumlah": r[4],
            "kabupaten": r[5],
            "batch": r[6],
            "file_path": file_path
        })
    return hasil

def list_kabupaten():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT nama_kabupaten FROM master_kabupaten ORDER BY nama_kabupaten ASC")
        return [r[0] for r in c.fetchall()]

# ==========================================
# 🔹 Hasil Penetapan (untuk MDT & Kanwil)
# ==========================================
def list_hasil_penetapan_by_role(role):
    with _conn() as conn:
        c = conn.cursor()
        if role == "mdt":
            c.execute("""
                SELECT nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                       jumlah_lulus, kabupaten, tanggal_penetapan
                FROM pengajuan
                WHERE status='Ditetapkan'
                ORDER BY id DESC
            """)
        else:  # Kanwil
            c.execute("""
                SELECT nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                       jumlah_lulus, kabupaten, tanggal_penetapan, verifikator
                FROM pengajuan
                WHERE status='Ditetapkan'
                ORDER BY id DESC
            """)
        return c.fetchall()


# ======================
# KANKEMENAG: VERIFIKASI
# ======================
def list_pengajuan_for_kemenag():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                   file_lulusan, status, kabupaten
            FROM pengajuan
            WHERE status = 'Menunggu'
            ORDER BY id DESC
        """)
        return c.fetchall()


# =========================================================
# 🔸 Fungsi update status verifikasi dari Kemenag
# =========================================================
def update_status_pengajuan(pengajuan_id, status, alasan=None, verifikator=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    status_clean = status.strip().lower()
    if status_clean in ["diverifikasi", "verifikasi", "setuju", "ya", "acc", "approve"]:
        status_final = "Diverifikasi"
    elif status_clean in ["tolak", "ditolak", "tidak", "no"]:
        status_final = "Ditolak"
    else:
        status_final = "Menunggu"

    with _conn() as conn:
        c = conn.cursor()

        # Ambil data pengajuan
        c.execute("SELECT nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus FROM pengajuan WHERE id=?", (pengajuan_id,))
        data = c.fetchone()
        nama_mdt, jenjang, tahun, jumlah_lulus = data if data else ("-", "-", "-", 0)

        # Update pengajuan
        c.execute("""
            UPDATE pengajuan
            SET status=?, alasan=?, verifikator=?, tanggal_verifikasi=?
            WHERE id=?
        """, (status_final, alasan, verifikator, now, pengajuan_id))

        # Simpan log riwayat di koneksi yang sama
        c.execute("""
            CREATE TABLE IF NOT EXISTS riwayat_verifikasi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pengajuan_id INTEGER,
                nama_mdt TEXT,
                jenjang TEXT,
                tahun TEXT,
                jumlah_lulus INTEGER,
                status TEXT,
                alasan TEXT,
                verifikator TEXT,
                tanggal_verifikasi TEXT
            )
        """)
        c.execute("""
            INSERT INTO riwayat_verifikasi
            (pengajuan_id, nama_mdt, jenjang, tahun, jumlah_lulus, status, alasan, verifikator, tanggal_verifikasi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pengajuan_id, nama_mdt, jenjang, tahun, jumlah_lulus, status_final, alasan, verifikator, now))

        conn.commit()
        
# =========================================
# 🔹 SIMPAN LOG RIWAYAT VERIFIKASI
# =========================================
def simpan_riwayat_verifikasi(pengajuan_id, nama_mdt, jenjang, tahun, jumlah_lulus, status, alasan, verifikator):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS riwayat_verifikasi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pengajuan_id INTEGER,
                nama_mdt TEXT,
                jenjang TEXT,
                tahun TEXT,
                jumlah_lulus INTEGER,
                status TEXT,
                alasan TEXT,
                verifikator TEXT,
                tanggal_verifikasi TEXT
            )
        """)
        c.execute("""
            INSERT INTO riwayat_verifikasi 
            (pengajuan_id, nama_mdt, jenjang, tahun, jumlah_lulus, status, alasan, verifikator, tanggal_verifikasi)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pengajuan_id, nama_mdt, jenjang, tahun, jumlah_lulus, status, alasan, verifikator, now))
        conn.commit()

# =========================================
# 🔹 RIWAYAT KHUSUS UNTUK HALAMAN RIWAYAT
# =========================================
def list_riwayat_verifikasi_kemenag():
    with _conn() as conn:
        c = conn.cursor()
        # Pastikan tabel riwayat ada (biar gak error no such table)
        c.execute("""
            CREATE TABLE IF NOT EXISTS riwayat_verifikasi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pengajuan_id INTEGER,
                nama_mdt TEXT,
                jenjang TEXT,
                tahun TEXT,
                status TEXT,
                alasan TEXT,
                verifikator TEXT,
                tanggal_verifikasi TEXT
            )
        """)

        # Ambil semua riwayat dengan urutan terbaru
        c.execute("""
            SELECT 
                nama_mdt,      -- [0]
                jenjang,       -- [1]
                tahun,         -- [2]
                NULL,          -- [3] (jumlah lulus tidak disimpan di sini)
                status,        -- [4]
                alasan,        -- [5]
                verifikator,   -- [6]
                tanggal_verifikasi -- [7]
            FROM riwayat_verifikasi
            ORDER BY tanggal_verifikasi DESC
        """)
        return c.fetchall()


