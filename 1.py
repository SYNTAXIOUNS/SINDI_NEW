import sqlite3
conn = sqlite3.connect("sindi.db")
c = conn.cursor()
c.execute("ALTER TABLE pengajuan ADD COLUMN tanggal_penetapan TEXT;")
conn.commit()
conn.close()
