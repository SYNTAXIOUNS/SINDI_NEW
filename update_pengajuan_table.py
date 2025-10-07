import sqlite3, os, datetime

DB_NAME = "sindi.db"

def add_column_if_not_exists(cursor, table_name, column_name, column_type):
    """Tambahkan kolom ke tabel jika belum ada."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        print(f"🆕 Kolom '{column_name}' berhasil ditambahkan ke tabel '{table_name}'.")

def init_db():
    # ===== KONEKSI DATABASE =====
    if os.path.exists(DB_NAME):
        print("⚠️ Database sudah ada, tidak akan dihapus.")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # ===== TABEL USERS =====
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        kode_mdt TEXT,
        wilayah TEXT
    )
    """)

    # ===== TABEL PENGAJUAN =====
    c.execute("""
    CREATE TABLE IF NOT EXISTS pengajuan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        FOREIGN KEY (mdt_id) REFERENCES users (id)
    )
    """)

    # ✅ Tambahkan kolom baru bila belum ada
    add_column_if_not_exists(c, "pengajuan", "alasan", "TEXT")
    add_column_if_not_exists(c, "pengajuan", "tanggal_verifikasi", "TEXT")
    add_column_if_not_exists(c, "pengajuan", "verifikator", "TEXT")

    # ===== TABEL NOMOR IJAZAH =====
    c.execute("""
    CREATE TABLE IF NOT EXISTS nomor_ijazah (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pengajuan_id INTEGER,
        nama_santri TEXT,
        nis TEXT,
        nomor_ijazah TEXT,
        tahun TEXT,
        jenjang TEXT,
        FOREIGN KEY (pengajuan_id) REFERENCES pengajuan (id)
    )
    """)

    # ===== ISI USER DEFAULT =====
    users = [
        ("mdt", "123", "mdt", "MDT001", "Kota Cimahi"),
        ("kemenag", "123", "kankemenag", None, "Kota Cimahi"),
        ("kanwil", "123", "kanwil", None, "Jawa Barat"),
        ("admin", "123", "admin", None, "Kanwil Jabar")
    ]
    c.executemany("""
        INSERT OR IGNORE INTO users (username, password, role, kode_mdt, wilayah)
        VALUES (?, ?, ?, ?, ?)
    """, users)

    conn.commit()
    conn.close()
    print("✅ Struktur database SINDI telah diperbarui sepenuhnya.")
    print("   Kolom tambahan: alasan, tanggal_verifikasi, verifikator")

if __name__ == "__main__":
    init_db()
