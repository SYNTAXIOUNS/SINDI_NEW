import sqlite3
conn = sqlite3.connect("instance/sindi.db")
c = conn.cursor()

c.execute("SELECT id, nama_mdt, status, alasan, tanggal_verifikasi FROM pengajuan")
for r in c.fetchall():
    print(r)
conn.close()