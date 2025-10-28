import sqlite3, os, datetime

DB_NAME = "sindi.db"

# =========================
# 🧱 Backup Database Lama
# =========================
if os.path.exists(DB_NAME):
    backup_name = f"sindi_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    os.rename(DB_NAME, backup_name)
    print(f"🗂️ Backup database lama dibuat → {backup_name}")

conn = sqlite3.connect(DB_NAME)
c = conn.cursor()

# =========================
# 🔸 USERS
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
# 🔸 MASTER KABUPATEN
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS master_kabupaten (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama_kabupaten TEXT NOT NULL UNIQUE,
    provinsi TEXT NOT NULL
)
""")

# =========================
# 🔸 PENGAJUAN MDT
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
    file_hasil TEXT,
    mdt_id INTEGER,
    kabupaten TEXT,
    alasan TEXT,
    tanggal_verifikasi TEXT,
    verifikator TEXT
)
""")

# =========================
# 🔸 NOMOR IJAZAH
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS nomor_ijazah (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pengajuan_id INTEGER,
    nama_santri TEXT,
    nis TEXT,
    nomor_ijazah TEXT,
    tahun TEXT,
    jenjang TEXT,
    FOREIGN KEY (pengajuan_id) REFERENCES pengajuan(id)
)
""")

# =========================
# 🔸 RIWAYAT VERIFIKASI
# =========================
c.execute("""
CREATE TABLE IF NOT EXISTS riwayat_verifikasi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pengajuan_id INTEGER,
    nama_mdt TEXT,
    jenjang TEXT,
    tahun_pelajaran TEXT,
    jumlah_lulus INTEGER,
    status TEXT,
    alasan TEXT,
    verifikator TEXT,
    tanggal_verifikasi TEXT,
    FOREIGN KEY (pengajuan_id) REFERENCES pengajuan(id)
)
""")

# =========================
# 🧩 TRIGGER OTOMATIS
# =========================
c.execute("""
CREATE TRIGGER IF NOT EXISTS after_pengajuan_status_update
AFTER UPDATE OF status ON pengajuan
BEGIN
    INSERT INTO riwayat_verifikasi (
        pengajuan_id,
        nama_mdt,
        jenjang,
        tahun_pelajaran,
        jumlah_lulus,
        status,
        alasan,
        verifikator,
        tanggal_verifikasi
    )
    VALUES (
        NEW.id,
        NEW.nama_mdt,
        NEW.jenjang,
        NEW.tahun_pelajaran,
        NEW.jumlah_lulus,
        NEW.status,
        NEW.alasan,
        NEW.verifikator,
        datetime('now', 'localtime')
    );
END;
""")

conn.commit()

# =========================
# 📍 MASTER DATA KABUPATEN
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
# 👤 USER AWAL SISTEM
# =========================
users = [
    ("admin", "123", "admin", None, "Kanwil Jawa Barat"),
    ("kanwil", "123", "kanwil", None, "Kanwil Jawa Barat"),
    ("kemenag", "123", "kankemenag", None, "Kemenag Kabupaten/Kota"),
    ("mdt", "123", "mdt", "MDT001", "Kota Cimahi"),
]
for u in users:
    c.execute("INSERT INTO users (username, password, role, kode_mdt, wilayah) VALUES (?, ?, ?, ?, ?)", u)

conn.commit()
conn.close()

print("✅ Database 'sindi.db' berhasil dibuat ulang dan siap digunakan untuk aplikasi SINDI.")
print("📦 Struktur tabel termasuk: users, master_kabupaten, pengajuan, nomor_ijazah, dan riwayat_verifikasi.")
print("🧠 Trigger aktif: otomatis mencatat setiap perubahan status pengajuan ke tabel riwayat_verifikasi.")
