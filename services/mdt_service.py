import sqlite3, datetime, os, uuid
import pandas as pd
from fpdf import FPDF
import datetime
import sqlite3
import os

DB_NAME = "sindi.db"

# ======================
# DATABASE HELPER
# ======================
def _conn():
    """Helper function untuk koneksi database SQLite"""
    return sqlite3.connect(DB_NAME)

# ======================
# MDT: PENGAJUAN BATCH
# ======================
def create_pengajuan_batch(mdt_user, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, file_lulusan_path):
    nomor_batch = f"BATCH-{mdt_user['kode_mdt']}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO pengajuan (nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, file_lulusan,
                                   tanggal_pengajuan, status, nomor_batch, mdt_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nama_mdt, jenjang, tahun_pelajaran, int(jumlah_lulus),
            file_lulusan_path, datetime.date.today().isoformat(),
            "Diajukan", nomor_batch, mdt_user["id"]
        ))
        conn.commit()
        return nomor_batch


def list_pengajuan_batch_by_mdt(mdt_id):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                   file_lulusan, tanggal_pengajuan, status
            FROM pengajuan
            WHERE mdt_id=?
            ORDER BY id DESC
        """, (mdt_id,))
        return c.fetchall()

# ======================
# KANKEMENAG: VERIFIKASI
# ======================
def list_pengajuan_for_kemenag():
    """Menampilkan semua pengajuan yang belum diverifikasi"""
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                   jumlah_lulus, tanggal_pengajuan, status, file_lulusan, rekomendasi_file
            FROM pengajuan
            WHERE status='Diajukan'
            ORDER BY tanggal_pengajuan DESC
        """)
        return c.fetchall()

import sqlite3

DB_NAME = "sindi.db"

def update_status_pengajuan(pengajuan_id, status, alasan=None, verifikator=None):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE pengajuan
            SET status = ?, alasan = ?, tanggal_verifikasi = ?, verifikator = ?
            WHERE id = ?
        """, (
            status,
            alasan,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            verifikator,
            pengajuan_id
        ))
        conn.commit()
        return True

def update_status_to_diverifikasi(pengajuan_id, rekomendasi_path):
    """Update status pengajuan jadi Diverifikasi dan simpan file rekomendasi"""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE pengajuan
                SET status = 'Diverifikasi',
                    rekomendasi_file = ?
                WHERE id = ?
            """, (rekomendasi_path, pengajuan_id))
            conn.commit()
        print(f"✅ Pengajuan {pengajuan_id} berhasil diverifikasi.")
        return True
    except Exception as e:
        print(f"❌ Gagal memperbarui pengajuan {pengajuan_id}: {e}")
        return False

# ======================
# KANWIL: PENETAPAN NOMOR IJAZAH
# ======================
def list_pengajuan_for_kanwil():
    """Daftar pengajuan yang siap ditetapkan (sudah diverifikasi)"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                   jumlah_lulus, file_lulusan, tanggal_pengajuan, status,
                   tanggal_verifikasi, verifikator, alasan
            FROM pengajuan
            WHERE status IN ('Diverifikasi', 'Ditolak')
            ORDER BY tanggal_pengajuan DESC
        """)
        return c.fetchall()

def update_status_pengajuan(pengajuan_id, status, alasan=None):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE pengajuan
            SET status=?, alasan=?
            WHERE id=?
        """, (status, alasan, pengajuan_id))
        conn.commit()

def generate_nomor_ijazah_batch(pengajuan_id):
    """Generate nomor ijazah otomatis sesuai struktur kolom DAFTAR PENETAPAN MDT"""
    import pandas as pd, os
    from datetime import datetime

    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT file_lulusan, jenjang, tahun_pelajaran, nama_mdt FROM pengajuan WHERE id=?", (pengajuan_id,))
        data = c.fetchone()
        if not data:
            raise Exception("Data pengajuan tidak ditemukan.")

        file_path, jenjang, tahun, nama_mdt = data
        if not os.path.exists(file_path):
            raise Exception(f"File Excel {file_path} tidak ditemukan.")

        # Mapping jenjang ke kode
        kode_jenjang = {"Ula": "I", "Wustha": "II", "Ulya": "III", "Al-Jami’ah": "IV"}.get(jenjang, "I")

        # Baca Excel (header otomatis)
        df = pd.read_excel(file_path)
        df = df.dropna(how='all')  # hapus baris kosong

        # Normalisasi nama kolom ke lowercase untuk pencarian fleksibel
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Cari kolom nama santri dan nomor induk santri
        nama_col = next((col for col in df.columns if "nama santri" in col), None)
        nis_col = next((col for col in df.columns if "nomor induk" in col or "nis" in col), None)

        if not nama_col or not nis_col:
            raise Exception("Kolom 'Nama santri' atau 'Nomor Induk Santri' tidak ditemukan di Excel!")

        # Hitung awal nomor ijazah
        c.execute("SELECT COUNT(*) FROM nomor_ijazah")
        start_count = c.fetchone()[0] or 0

        # Generate nomor ijazah
        nomor_ijazah_list, generated_rows = [], []
        for i, row in df.iterrows():
            nomor_urut = str(start_count + i + 1).zfill(6)
            nomor_ijazah = f"MDT-12-{kode_jenjang}-{tahun}-{nomor_urut}"
            nomor_ijazah_list.append(nomor_ijazah)
            generated_rows.append((
                pengajuan_id,
                str(row[nama_col]).strip(),
                str(row[nis_col]).strip(),
                nomor_ijazah,
                tahun,
                jenjang
            ))

        # Tambahkan kolom baru ke Excel
        df["Nomor Ijazah"] = nomor_ijazah_list

        hasil_dir = "hasil_excel"
        os.makedirs(hasil_dir, exist_ok=True)
        output_file = f"HASIL_{nama_mdt}_{tahun}_{jenjang}.xlsx"
        output_path = os.path.join(hasil_dir, output_file)
        df.to_excel(output_path, index=False)

        # Simpan ke DB
        c.executemany("""
            INSERT INTO nomor_ijazah (pengajuan_id, nama_santri, nis, nomor_ijazah, tahun, jenjang)
            VALUES (?, ?, ?, ?, ?, ?)
        """, generated_rows)
        c.execute("UPDATE pengajuan SET status='Ditetapkan' WHERE id=?", (pengajuan_id,))
        conn.commit()

        print(f"✅ {len(generated_rows)} nomor ijazah berhasil dibuat untuk {nama_mdt}")
        print(f"📁 File hasil: {output_path}")

        return output_file

# ======================
# MDT: LIHAT HASIL PENETAPAN
# ======================
def get_nomor_ijazah_by_pengajuan(pengajuan_id):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT nama_santri, nis, nomor_ijazah, tahun, jenjang
            FROM nomor_ijazah
            WHERE pengajuan_id=?
            ORDER BY id ASC
        """, (pengajuan_id,))
        return c.fetchall()

# ======================
# EXPORT HASIL PENETAPAN
# ======================
def export_nomor_ijazah_excel(pengajuan_id, output_path):
    data = get_nomor_ijazah_by_pengajuan(pengajuan_id)
    df = pd.DataFrame(data, columns=["Nama Santri", "NIS", "Nomor Ijazah", "Tahun", "Jenjang"])
    df.index += 1
    df.to_excel(output_path, index_label="No")
    return output_path

def export_nomor_ijazah_pdf(pengajuan_id, output_path, nama_mdt="MDT"):
    data = get_nomor_ijazah_by_pengajuan(pengajuan_id)
    if not data:
        raise Exception("Belum ada data nomor ijazah untuk pengajuan ini.")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"DAFTAR NOMOR IJAZAH {nama_mdt}", ln=True, align="C")
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 10, f"Jumlah Santri: {len(data)}", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(10, 8, "No", 1)
    pdf.cell(60, 8, "Nama Santri", 1)
    pdf.cell(40, 8, "NIS", 1)
    pdf.cell(55, 8, "Nomor Ijazah", 1)
    pdf.cell(25, 8, "Jenjang", 1)
    pdf.ln()

    pdf.set_font("Arial", "", 9)
    for i, (nama, nis, nomor, tahun, jenjang) in enumerate(data, start=1):
        pdf.cell(10, 8, str(i), 1)
        pdf.cell(60, 8, str(nama)[:25], 1)
        pdf.cell(40, 8, str(nis), 1)
        pdf.cell(55, 8, str(nomor), 1)
        pdf.cell(25, 8, str(jenjang), 1)
        pdf.ln()

    pdf.output(output_path)
    return output_path

def _conn():
    return sqlite3.connect(DB_NAME)

def get_jenjang_kode(jenjang):
    """Konversi nama jenjang menjadi kode"""
    jenjang_map = {
        "Ula": "I",
        "Wustha": "II",
        "Ulya": "III"
    }
    return jenjang_map.get(jenjang, "I")  # default I

def generate_nomor_ijazah_from_excel(pengajuan_id, kode_mdt, tahun, jenjang):
    """Generate nomor ijazah otomatis untuk setiap santri dari file Excel"""
    with _conn() as conn:
        c = conn.cursor()

        # Ambil path file Excel dari pengajuan
        c.execute("SELECT file_lulusan FROM pengajuan WHERE id=?", (pengajuan_id,))
        result = c.fetchone()
        if not result:
            raise Exception("File lulusan tidak ditemukan untuk pengajuan ini.")
        file_path = result[0]

        if not os.path.exists(file_path):
            raise Exception(f"File tidak ditemukan di path: {file_path}")

        # Baca Excel MDT
        df = pd.read_excel(file_path)

        # Pastikan ada kolom yang benar
        if not {'Nama', 'NIS'}.issubset(df.columns):
            raise Exception("File Excel harus memiliki kolom 'Nama' dan 'NIS'.")

        # Ekstrak kode angka dari kode MDT (misal MDT012 -> 12)
        kode_angka = ''.join(filter(str.isdigit, kode_mdt)) or "00"
        kode_jenjang = get_jenjang_kode(jenjang)

        nomor_list = []
        for i, row in enumerate(df.itertuples(index=False), start=1):
            nomor_urut = str(i).zfill(6)
            nomor_ijazah = f"MDT-{kode_angka}-{kode_jenjang}-{tahun}-{nomor_urut}"
            nomor_list.append((pengajuan_id, getattr(row, "Nama"), str(getattr(row, "NIS")),
                               nomor_ijazah, tahun, jenjang))

        # Simpan ke tabel nomor_ijazah
        c.executemany("""
            INSERT INTO nomor_ijazah (pengajuan_id, nama_santri, nis, nomor_ijazah, tahun, jenjang)
            VALUES (?, ?, ?, ?, ?, ?)
        """, nomor_list)

        # Update status pengajuan
        c.execute("UPDATE pengajuan SET status='Ditetapkan' WHERE id=?", (pengajuan_id,))
        conn.commit()
        
        
def list_hasil_nomor_ijazah_by_mdt(mdt_kode):
    """Ambil seluruh daftar nomor ijazah milik MDT berdasarkan kode MDT"""
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT ni.id, p.nomor_batch, ni.nama_santri, ni.nis, ni.nomor_ijazah, ni.tahun, ni.jenjang
            FROM nomor_ijazah ni
            JOIN pengajuan p ON ni.pengajuan_id = p.id
            JOIN users u ON p.mdt_id = u.id
            WHERE u.kode_mdt = ?
            ORDER BY ni.nomor_ijazah ASC
        """, (mdt_kode,))
        return c.fetchall()

def list_hasil_penetapan(kode_mdt=None):
    """Ambil daftar pengajuan yang sudah ditetapkan (dengan file hasil)"""
    with _conn() as conn:
        c = conn.cursor()
        if kode_mdt:
            c.execute("""
                SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, nomor_batch
                FROM pengajuan
                WHERE status='Ditetapkan' AND nama_mdt=?
                ORDER BY id DESC
            """, (kode_mdt,))
        else:
            c.execute("""
                SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, nomor_batch
                FROM pengajuan
                WHERE status='Ditetapkan'
                ORDER BY id DESC
            """)
        data = c.fetchall()
        results = []
        for row in data:
            pengajuan_id = row[0]
            hasil_path = f"hasil_excel/HASIL_{row[1]}_{row[3]}_{row[2]}.xlsx"
            if os.path.exists(hasil_path):
                results.append({
                    "id": pengajuan_id,
                    "nama_mdt": row[1],
                    "jenjang": row[2],
                    "tahun": row[3],
                    "jumlah": row[4],
                    "batch": row[5],
                    "file_path": hasil_path
                })
        return results

def get_nama_mdt_by_kode(kode_mdt):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE kode_mdt=?", (kode_mdt,))
        row = c.fetchone()
        return row[0] if row else kode_mdt

def list_kabupaten():
    import sqlite3
    from app import DB_NAME

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # ambil kolom nama_kabupaten saja
        c.execute("SELECT nama_kabupaten FROM master_kabupaten ORDER BY nama_kabupaten ASC")
        hasil = c.fetchall()

    # ubah hasil tuple [(‘Kabupaten Bandung’,), (‘Kota Cimahi’,)] menjadi list ['Kabupaten Bandung', 'Kota Cimahi']
    kabupaten_list = [row[0] for row in hasil]

    print("DEBUG Kab:", kabupaten_list[:5])  # <-- opsional, buat ngecek isi di console
    return kabupaten_list
