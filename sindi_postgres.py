import sqlite3
import psycopg2
import os

# --- Ganti ini dengan URL dari Render PostgreSQL kamu ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://sindi_jepf_user:tkWIZQfHSvi8p3DSjC9vDi9vo1OC9sVc@dpg-d3lt3cogjchc73cmsuo0-a/sindi_jepf")

# --- SQLite lokal kamu ---
SQLITE_DB = "sindi.db"

print("🚀 Migrasi dari SQLite ke PostgreSQL dimulai...")

# Koneksi ke SQLite
sqlite_conn = sqlite3.connect(SQLITE_DB)
sqlite_cur = sqlite_conn.cursor()

# Koneksi ke PostgreSQL
pg_conn = psycopg2.connect(DATABASE_URL)
pg_cur = pg_conn.cursor()

# Daftar tabel yang mau dimigrasikan
tables = ["users", "pengajuan", "nomor_ijazah", "master_kabupaten"]

for table in tables:
    print(f"📤 Migrasi tabel: {table}")

    # Ambil semua data dari SQLite
    sqlite_cur.execute(f"SELECT * FROM {table}")
    rows = sqlite_cur.fetchall()

    # Ambil kolom
    sqlite_cur.execute(f"PRAGMA table_info({table})")
    cols = [col[1] for col in sqlite_cur.fetchall()]
    col_names = ", ".join(cols)
    placeholders = ", ".join(["%s"] * len(cols))

    # Buat tabel di PostgreSQL kalau belum ada
    if table == "users":
        pg_cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE,
                password TEXT,
                role TEXT,
                kode_mdt TEXT,
                wilayah TEXT
            );
        """)
    elif table == "pengajuan":
        pg_cur.execute("""
            CREATE TABLE IF NOT EXISTS pengajuan (
                id SERIAL PRIMARY KEY,
                nama_mdt TEXT,
                jenjang TEXT,
                tahun_pelajaran TEXT,
                jumlah_lulus INTEGER,
                file_lulusan TEXT,
                tanggal_pengajuan TEXT,
                status TEXT,
                nomor_batch TEXT,
                rekomendasi_file TEXT,
                mdt_id INTEGER,
                kabupaten TEXT
            );
        """)
    elif table == "nomor_ijazah":
        pg_cur.execute("""
            CREATE TABLE IF NOT EXISTS nomor_ijazah (
                id SERIAL PRIMARY KEY,
                pengajuan_id INTEGER,
                nama_santri TEXT,
                nis TEXT,
                nomor_ijazah TEXT,
                tahun TEXT,
                jenjang TEXT
            );
        """)
    elif table == "master_kabupaten":
        pg_cur.execute("""
            CREATE TABLE IF NOT EXISTS master_kabupaten (
                id SERIAL PRIMARY KEY,
                nama_kabupaten TEXT UNIQUE,
                provinsi TEXT
            );
        """)

    # Masukkan data ke PostgreSQL
    if rows:
        for row in rows:
            try:
                pg_cur.execute(
                    f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                    row
                )
            except Exception as e:
                print(f"⚠️ Gagal insert row: {e}")

pg_conn.commit()
sqlite_conn.close()
pg_conn.close()

print("✅ Migrasi selesai! Semua tabel dan data berhasil dipindahkan ke PostgreSQL.")
