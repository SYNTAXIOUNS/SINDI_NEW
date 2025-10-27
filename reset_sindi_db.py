import sqlite3, os, datetime

DB_NAME = "sindi.db"

# =========================
# 🧱 Backup Database Lama
# =========================
if os.path.exists(DB_NAME):
    os.rename(DB_NAME, f"sindi_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    print("🗂️ Backup dibuat.")

conn = sqlite3.connect(DB_NAME)
c = conn.cursor()

# =========================
# 🔸 Tabel USERS
# =========================
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

# =========================
# 🔸 Tabel MASTER KABUPATEN
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS master_kabupaten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_kabupaten TEXT NOT NULL UNIQUE,
    provinsi TEXT NOT NULL
)
""")

# =========================
# 🔸 Tabel PENGAJUAN
# =========================
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

# =========================
# 🔸 Tabel NOMOR IJAZAH
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS nomor_ijazah (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pengajuan_id INTEGER,
    nama_santri TEXT,
    nis TEXT,
    nomor_ijazah TEXT,
    tahun TEXT,
    jenjang TEXT
)
""")

# =========================
# 🔸 Tabel RIWAYAT VERIFIKASI
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS riwayat_verifikasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pengajuan_id INTEGER,
    nama_mdt TEXT,
    status TEXT,
    alasan TEXT,
    verifikator TEXT,
    tanggal_verifikasi TEXT
)
""")

# =========================
# 🧩 Trigger: Simpan otomatis ke riwayat saat verifikasi berubah
# =========================
c.execute("""
CREATE TRIGGER IF NOT EXISTS after_pengajuan_update
AFTER UPDATE OF status ON pengajuan
BEGIN
    INSERT INTO riwayat_verifikasi (pengajuan_id, nama_mdt, status, alasan, verifikator, tanggal_verifikasi)
    VALUES (
        NEW.id,
        NEW.nama_mdt,
        NEW.status,
        NEW.alasan,
        NEW.verifikator,
        datetime('now', 'localtime')
    );
END;
""")

conn.commit()

# =========================
# 📍 ISI MASTER KABUPATEN
# =========================
kabupaten_jabar = [
    "Kabupaten Bandung", "Kabupaten Bandung Barat", "Kabupaten Bekasi", "Kabupaten Bogor",
    "Kabupaten Ciamis", "Kabupaten Cianjur", "Kabupaten Cirebon", "Kabupaten Garut",
    "Kabupaten Indramayu", "Kabupaten Karawang", "Kabupaten Kuningan", "Kabupaten Majalengka",
    "Kabupaten Pangandaran", "Kabupaten Purwakarta", "Kabupaten Subang", "Kabupaten Sukabumi",
    "Kabupaten Sumedang", "Kabupaten Tasikmalaya", "Kota Bandung", "Kota Banjar",
    "Kota Bekasi", "Kota Bogor", "Kota Cimahi", "Kota Cirebon", "Kota Depok",
    "Kota Sukabumi", "Kota Tasikmalaya"
]
for k in kabupaten_jabar:
    c.execute("INSERT INTO master_kabupaten (nama_kabupaten, provinsi) VALUES (?, ?)", (k, "Jawa Barat"))

conn.commit()

# =========================
# 👤 USER AWAL
# =========================
users = [
    ("admin", "123", "admin", None, "Kanwil Jawa Barat"),
    ("kanwil", "123", "kanwil", None, "Kanwil Jawa Barat"),
    ("kemenag", "123", "kemenag", None, "Jawa barat"),
    ("mdt", "123", "mdt", "MDT001", "Jawa Barat"),
]
for u in users:
    c.execute("INSERT INTO users (username, password, role, kode_mdt, wilayah) VALUES (?, ?, ?, ?, ?)", u)

conn.commit()
conn.close()

print("✅ Database 'sindi.db' berhasil dibuat ulang dan siap digunakan untuk aplikasi SINDI.")
