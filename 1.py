import sqlite3

conn = sqlite3.connect("sindi.db")
c = conn.cursor()

# Tambahkan kolom jika belum ada
try:
    c.execute("ALTER TABLE pengajuan ADD COLUMN file_hasil TEXT")
    print("✅ Kolom 'file_hasil' berhasil ditambahkan ke tabel pengajuan.")
except sqlite3.OperationalError:
    print("ℹ️ Kolom 'file_hasil' sudah ada, dilewati.")

conn.commit()
conn.close()
