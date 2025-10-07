import sqlite3, datetime, os, uuid
import pandas as pd
from fpdf import FPDF
import datetime
import sqlite3

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

def generate_nomor_ijazah_batch(pengajuan_id):
    """Baca file Excel lulusan, buat nomor ijazah otomatis, simpan ke tabel nomor_ijazah"""
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT file_lulusan, jenjang, tahun_pelajaran FROM pengajuan WHERE id=?", (pengajuan_id,))
        data = c.fetchone()
        if not data:
            raise Exception("Data pengajuan tidak ditemukan.")

        file_path, jenjang, tahun = data

        # Mapping jenjang ke kode singkat
        kode_jenjang = {
            "Ula": "I",
            "Wustha": "II",
            "Ulya": "III",
            "Al-Jami’ah": "IV"
        }.get(jenjang, "I")

        # Baca file Excel santri
        df = pd.read_excel(file_path)
        nama_col = df.columns[0]
        nis_col = df.columns[1]

        # Generate nomor ijazah
        c.execute("SELECT COUNT(*) FROM nomor_ijazah")
        start_count = c.fetchone()[0]

        generated_rows = []
        for i, row in df.iterrows():
            nomor_urut = str(start_count + i + 1).zfill(6)
            nomor_ijazah = f"MDT-12-{kode_jenjang}-{tahun}-{nomor_urut}"
            generated_rows.append((
                pengajuan_id,
                str(row[nama_col]),
                str(row[nis_col]),
                nomor_ijazah,
                tahun,
                jenjang
            ))

        # Simpan ke tabel nomor_ijazah
        c.executemany("""
            INSERT INTO nomor_ijazah (pengajuan_id, nama_santri, nis, nomor_ijazah, tahun, jenjang)
            VALUES (?, ?, ?, ?, ?, ?)
        """, generated_rows)

        # Update status pengajuan
        c.execute("UPDATE pengajuan SET status='Ditetapkan' WHERE id=?", (pengajuan_id,))
        conn.commit()
        return len(generated_rows)

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
