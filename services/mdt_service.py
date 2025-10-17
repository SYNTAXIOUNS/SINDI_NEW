# services/mdt_service.py
import sqlite3, datetime, os, pandas as pd
from fpdf import FPDF

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "sindi.db")


# ======================================
# HYBRID DB: PostgreSQL (Render) / SQLite (Local)
# ======================================
DATABASE_URL = os.getenv("DATABASE_URL")
IS_POSTGRES = DATABASE_URL is not None  # ✅ Tambahkan baris ini
DB_NAME = "sindi.db"

def _conn():
    if IS_POSTGRES:
        result = urlparse(DATABASE_URL)
        return psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
    return sqlite3.connect(DB_NAME)
# ======================
# KONEKSI DATABASE
# ======================
def _conn():
    """Koneksi SQLite"""
    return sqlite3.connect(DB_NAME)

# ======================
# MIGRASI / INIT
# ======================
def init_db():
    with _conn() as conn:
        c = conn.cursor()
        # pastikan kolom ada
        for col, tipe in [
            ("alasan", "TEXT"),
            ("kabupaten", "TEXT"),
            ("tanggal_verifikasi", "TEXT"),
            ("verifikator", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE pengajuan ADD COLUMN {col} {tipe}")
            except sqlite3.OperationalError:
                pass  # kolom sudah ada
        conn.commit()

# ======================
# MDT: PENGAJUAN
# ======================
def create_pengajuan_batch(mdt_user, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, file_lulusan_path):
    import datetime
    from app_gateway import DB_NAME
    import sqlite3

    nomor_batch = f"BATCH_{mdt_user['kode_mdt']}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    kabupaten = mdt_user.get("wilayah", "-")

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO pengajuan (
                nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                file_lulusan, tanggal_pengajuan, status, nomor_batch,
                rekomendasi_file, mdt_id, kabupaten, alasan,
                tanggal_verifikasi, verifikator
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            nama_mdt,
            jenjang,
            tahun_pelajaran,
            jumlah_lulus,
            file_lulusan_path,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Menunggu",
            nomor_batch,
            None,
            mdt_user["id"],
            kabupaten,
            None,
            None,
            None
        ))
        conn.commit()
    return nomor_batch


def list_pengajuan_batch_by_mdt(mdt_id):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                   jumlah_lulus, file_lulusan, status, kabupaten
            FROM pengajuan
            WHERE mdt_id=? ORDER BY id DESC
        """, (mdt_id,))
        return c.fetchall()

# ======================
# KANKEMENAG: VERIFIKASI
# ======================
def list_pengajuan_for_kemenag():
    import sqlite3
    from app_gateway import DB_NAME

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                   file_lulusan, status, kabupaten
            FROM pengajuan
            WHERE status = 'Menunggu'
            ORDER BY id DESC
        """)
        return c.fetchall()

# =========================================================
# 🔸 Fungsi update status verifikasi dari Kemenag
# =========================================================
def update_status_pengajuan(pengajuan_id, status, alasan=None, verifikator=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Normalisasi status dengan aman
    status_clean = status.strip().lower()
    if status_clean in ["diverifikasi", "verifikasi", "setuju", "ya", "acc", "approve"]:
        status_final = "Diverifikasi"
    elif status_clean in ["tolak", "ditolak", "tidak", "no"]:
        status_final = "Ditolak"
    else:
        status_final = "Menunggu"

    with _conn() as conn:
        c = conn.cursor()

        # Pastikan kolom tambahan ada
        for col, tipe in [
            ("alasan", "TEXT"),
            ("verifikator", "TEXT"),
            ("tanggal_verifikasi", "TEXT")
        ]:
            try:
                c.execute(f"ALTER TABLE pengajuan ADD COLUMN {col} {tipe}")
            except sqlite3.OperationalError:
                pass

        # Simpan perubahan
        c.execute("""
            UPDATE pengajuan
            SET status=?, alasan=?, verifikator=?, tanggal_verifikasi=?
            WHERE id=?
        """, (status_final, alasan, verifikator, now, pengajuan_id))
        conn.commit()

# ======================
# KANWIL: PENETAPAN NOMOR IJAZAH
# ======================
def list_pengajuan_for_kanwil():
    """Menampilkan hanya yang sudah diverifikasi oleh Kemenag."""
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
                   file_lulusan, status, kabupaten, alasan, verifikator, tanggal_verifikasi
            FROM pengajuan
            WHERE status = 'Diverifikasi'
            ORDER BY id DESC
        """)
        return c.fetchall()


# =========================================================
# 🔸 Fungsi penetapan dari Kanwil
# =========================================================
# ==========================================
# 🔹 Penetapan oleh Kanwil
# ==========================================
def tetapkan_pengajuan(pengajuan_id):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE pengajuan
            SET status=%s, tanggal_penetapan=%s
            WHERE id=%s
        """ if IS_POSTGRES else """
            UPDATE pengajuan
            SET status=?, tanggal_penetapan=?
            WHERE id=?
        """, ("Ditetapkan", now, pengajuan_id))
        conn.commit()

def generate_nomor_ijazah_batch(pengajuan_id):
    """Generate nomor ijazah dari file Excel"""
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT file_lulusan, jenjang, tahun_pelajaran, nama_mdt FROM pengajuan WHERE id=?", (pengajuan_id,))
        data = c.fetchone()
        if not data:
            raise Exception("Data pengajuan tidak ditemukan.")

        file_path, jenjang, tahun, nama_mdt = data
        if not os.path.exists(file_path):
            raise Exception(f"File Excel {file_path} tidak ditemukan.")

        df = pd.read_excel(file_path)
        df.columns = [str(x).strip().lower() for x in df.columns]

        nama_col = next((col for col in df.columns if "nama" in col), None)
        nis_col = next((col for col in df.columns if "nis" in col or "nomor induk" in col), None)
        if not nama_col or not nis_col:
            raise Exception("File Excel harus memiliki kolom 'Nama' dan 'NIS'.")

        kode_jenjang = {"Ula": "I", "Wustha": "II", "Ulya": "III"}.get(jenjang, "I")

        c.execute("SELECT COUNT(*) FROM nomor_ijazah")
        start = c.fetchone()[0] or 0

        nomor_list = []
        for i, row in df.iterrows():
            urut = str(start + i + 1).zfill(6)
            no_ijazah = f"MDT-12-{kode_jenjang}-{tahun}-{urut}"
            nomor_list.append((pengajuan_id, row[nama_col], str(row[nis_col]), no_ijazah, tahun, jenjang))
        df["Nomor Ijazah"] = [n[3] for n in nomor_list]

        os.makedirs("hasil_excel", exist_ok=True)
        output = f"hasil_excel/HASIL_{nama_mdt}_{tahun}_{jenjang}.xlsx"
        df.to_excel(output, index=False)

        c.executemany("""
            INSERT INTO nomor_ijazah (pengajuan_id, nama_santri, nis, nomor_ijazah, tahun, jenjang)
            VALUES (?, ?, ?, ?, ?, ?)
        """, nomor_list)
        c.execute("UPDATE pengajuan SET status='Ditetapkan' WHERE id=?", (pengajuan_id,))
        conn.commit()

        return output


# ======================
# MDT & KANWIL: HASIL
# ======================
def get_nomor_ijazah_by_pengajuan(pengajuan_id):
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT nama_santri, nis, nomor_ijazah, tahun, jenjang
            FROM nomor_ijazah WHERE pengajuan_id=? ORDER BY id ASC
        """, (pengajuan_id,))
        return c.fetchall()


def list_hasil_penetapan(kode_mdt=None):
    with _conn() as conn:
        c = conn.cursor()
        if kode_mdt:
            c.execute("""
                SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, nomor_batch, kabupaten
                FROM pengajuan WHERE status='Ditetapkan' AND nama_mdt=? ORDER BY id DESC
            """, (kode_mdt,))
        else:
            c.execute("""
                SELECT id, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, nomor_batch, kabupaten
                FROM pengajuan WHERE status='Ditetapkan' ORDER BY id DESC
            """)
        data = c.fetchall()
        hasil = []
        for row in data:
            fpath = f"hasil_excel/HASIL_{row[1]}_{row[3]}_{row[2]}.xlsx"
            if os.path.exists(fpath):
                hasil.append({
                    "id": row[0],
                    "nama_mdt": row[1],
                    "jenjang": row[2],
                    "tahun": row[3],
                    "jumlah": row[4],
                    "batch": row[5],
                    "kabupaten": row[6],
                    "file_path": fpath
                })
        return hasil


def list_kabupaten():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("SELECT nama_kabupaten FROM master_kabupaten ORDER BY nama_kabupaten ASC")
        return [r[0] for r in c.fetchall()]

# ==========================================
# 🔹 Hasil Penetapan (untuk MDT & Kanwil)
# ==========================================
def list_hasil_penetapan_by_role(role):
    with _conn() as conn:
        c = conn.cursor()
        if role == "mdt":
            c.execute("""
                SELECT nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                       jumlah_lulus, kabupaten, tanggal_penetapan
                FROM pengajuan
                WHERE status='Ditetapkan'
                ORDER BY id DESC
            """)
        else:  # Kanwil
            c.execute("""
                SELECT nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                       jumlah_lulus, kabupaten, tanggal_penetapan, verifikator
                FROM pengajuan
                WHERE status='Ditetapkan'
                ORDER BY id DESC
            """)
        return c.fetchall()


# ==========================================
# 🔹 Riwayat Verifikasi untuk Kemenag
# ==========================================
def list_riwayat_verifikasi_kemenag():
    with _conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT nomor_batch, nama_mdt, jenjang, tahun_pelajaran,
                   jumlah_lulus, status, kabupaten, alasan, verifikator,
                   tanggal_verifikasi
            FROM pengajuan
            WHERE status IN ('Diverifikasi', 'Ditolak')
            ORDER BY tanggal_verifikasi DESC
        """)
        return c.fetchall()
