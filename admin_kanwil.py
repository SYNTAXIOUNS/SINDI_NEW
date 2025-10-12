import sqlite3
conn = sqlite3.connect("sindi.db")
c = conn.cursor()

# Tambahkan admin utama
c.execute("""
INSERT INTO users (username, password, role, kode_mdt, nama_mdt, wilayah)
VALUES ('admin', 'admin123', 'admin', NULL, 'Admin Kanwil', 'KANWIL JAWA BARAT')
""")

# Tambahkan akun Kanwil
c.execute("""
INSERT INTO users (username, password, role, kode_mdt, nama_mdt, wilayah)
VALUES ('kanwil', '123', 'kanwil', NULL, 'Kanwil Jabar', 'KANWIL JAWA BARAT')
""")

conn.commit()
conn.close()
print("✅ Admin dan Kanwil berhasil ditambahkan")
