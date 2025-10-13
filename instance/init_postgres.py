# ===============================================
# Inisialisasi PostgreSQL di Render (tanpa SQLite)
# ===============================================
import os
import psycopg2
from urllib.parse import urlparse

DATABASE_URL = os.getenv("postgresql://sindi_jepf_user:tkWIZQfHSvi8p3DSjC9vDi9vo1OC9sVc@dpg-d3lt3cogjchc73cmsuo0-a.singapore-postgres.render.com/sindi_jepf")
if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL belum diset di Render!")

result = urlparse(DATABASE_URL)
conn = psycopg2.connect(
    database=result.path[1:],
    user=result.username,
    password=result.password,
    host=result.hostname,
    port=result.port
)
cur = conn.cursor()

print("🚀 Membuat tabel di PostgreSQL...")

# === Buat tabel users ===
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    kode_mdt TEXT,
    wilayah TEXT
)
""")

# === Buat tabel pengajuan ===
cur.execute("""
CREATE TABLE IF NOT EXISTS pengajuan (
    id SERIAL PRIMARY KEY,
    nama_mdt TEXT,
    jenjang TEXT,
    tahun_pelajaran TEXT,
    jumlah_lulus INTEGER,
    file_lulusan TEXT,
    tanggal_pengajuan TIMESTAMP,
    status TEXT,
    nomor_batch TEXT,
    rekomendasi_file TEXT,
    mdt_id INTEGER,
    kabupaten TEXT
)
""")

# === Buat tabel nomor_ijazah ===
cur.execute("""
CREATE TABLE IF NOT EXISTS nomor_ijazah (
    id SERIAL PRIMARY KEY,
    pengajuan_id INTEGER,
    nama_santri TEXT,
    nis TEXT,
    nomor_ijazah TEXT,
    tahun TEXT,
    jenjang TEXT
)
""")

# === Tambahkan akun default ===
cur.execute("""
INSERT INTO users (username, password, role, kode_mdt, wilayah)
VALUES
('admin', '123', 'admin', NULL, 'Kanwil Jabar'),
('kanwil', '123', 'kanwil', NULL, 'Jawa Barat'),
('kemenag', '123', 'kankemenag', NULL, 'Kota Bandung')
ON CONFLICT (username) DO NOTHING;
""")

conn.commit()
print("✅ Semua tabel berhasil dibuat di PostgreSQL!")
cur.close()
conn.close()
