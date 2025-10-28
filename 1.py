import sqlite3

conn = sqlite3.connect("sindi.db")
c = conn.cursor()

# Tambahkan kolom jika belum ada
try:
    c.execute("ALTER TABLE riwayat_verifikasi ADD COLUMN tahun INTEGER")
    print("✅ Kolom 'tahun' berhasil ditambahkan ke tabel pengajuan.")
except sqlite3.OperationalError:
    print("ℹ️ Kolom 'tahun' sudah ada, dilewati.")

conn.commit()
conn.close()
