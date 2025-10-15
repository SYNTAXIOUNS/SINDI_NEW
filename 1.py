import sqlite3
conn = sqlite3.connect("sindi.db")
c = conn.cursor()

# Kolom tambahan untuk tracking verifikasi
for col in ["alasan", "verifikator", "tanggal_verifikasi"]:
    try:
        c.execute(f"ALTER TABLE pengajuan ADD COLUMN {col} TEXT;")
        print(f"✅ Kolom {col} ditambahkan.")
    except sqlite3.OperationalError:
        print(f"ℹ️ Kolom {col} sudah ada.")

conn.commit()
conn.close()
