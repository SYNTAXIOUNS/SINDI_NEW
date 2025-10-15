import sqlite3, os, datetime

DB_NAME = "sindi.db"

# Backup dulu jika ada
if os.path.exists(DB_NAME):
    os.rename(DB_NAME, f"sindi_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    print("🗂️ Backup dibuat.")

# Buat database baru
conn = sqlite3.connect(DB_NAME)
c = conn.cursor()

# === USERS ===
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    role TEXT NOT NULL,
    kode_mdt TEXT,
    wilayah TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# === MASTER KABUPATEN ===
c.execute("""
CREATE TABLE IF NOT EXISTS master_kabupaten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_kabupaten TEXT NOT NULL UNIQUE,
    provinsi TEXT NOT NULL
)
""")

# === PENGAJUAN ===
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
    kabupaten TEXT,
    alasan TEXT,
    tanggal_verifikasi TEXT,
    verifikator TEXT
)
""")

conn.commit()

# === ISI MASTER KABUPATEN JAWA BARAT ===
kabupaten_jabar = [
    "Kabupaten Bandung", "Kabupaten Bandung Barat", "Kabupaten Bekasi", "Kabupaten Bogor",
    "Kabupaten Ciamis", "Kabupaten Cianjur", "Kabupaten Cirebon", "Kabupaten Garut",
    "Kabupaten Indramayu", "Kabupaten Karawang", "Kabupaten Kuningan", "Kabupaten Majalengka",
    "Kabupaten Pangandaran", "Kabupaten Purwakarta", "Kabupaten Subang", "Kabupaten Sukabumi",
    "Kabupaten Sumedang", "Kabupaten Tasikmalaya", "Kota Bandung", "Kota Banjar",
    "Kota Bekasi", "Kota Bogor", "Kota Cimahi", "Kota Cirebon", "Kota Depok", "Kota Sukabumi", "Kota Tasikmalaya"
]
for k in kabupaten_jabar:
    c.execute("INSERT INTO master_kabupaten (nama_kabupaten, provinsi) VALUES (?, ?)", (k, "Jawa Barat"))

conn.commit()

# === BUAT USER AWAL ===
users = [
    ("admin", "123", "admin", None, "Kanwil Jawa Barat"),
    ("kanwil", "123", "kanwil", None, "Kanwil Jawa Barat"),
    ("kemenag", "123", "kankemenag", None, "Kabupaten Tasikmalaya"),
    ("mdt", "123", "mdt", "MDT001", "Kabupaten Tasikmalaya"),
]
for u in users:
    c.execute("INSERT INTO users (username, password, role, kode_mdt, wilayah) VALUES (?, ?, ?, ?, ?)", u)

conn.commit()
conn.close()

print("✅ Database 'sindi.db' berhasil dibuat ulang dengan struktur baru & data dasar.")
