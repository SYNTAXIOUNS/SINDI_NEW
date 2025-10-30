from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3, os, datetime, psycopg2
from urllib.parse import urlparse
from werkzeug.utils import secure_filename

# ====== SERVICES (pastikan fungsi-fungsi ini ada di services/*.py) ======
from services.auth_service import login_user, logout_user, current_user, require_role
from services.admin_service import list_users, create_user
from services.mdt_service import (
    create_pengajuan_batch,
    list_pengajuan_batch_by_mdt,
    init_db,
    list_pengajuan_for_kemenag,
    update_status_pengajuan,
    list_pengajuan_for_kanwil,
    generate_nomor_ijazah_batch,
    list_hasil_penetapan,
    list_kabupaten
)

from flask import send_file, jsonify
from flask import send_from_directory, abort
from flask import render_template
import pandas as pd
from urllib.parse import unquote

# ====== APP CONFIG ======
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY", "sangat_rahasia")
app.config["PROPAGATE_EXCEPTIONS"] = True

# =======================================
# Database Path (Render + Lokal Compatible)
# =======================================

# Tentukan base folder aplikasi
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TMP_DIR = "/tmp"
UPLOAD_DIR = os.path.join(TMP_DIR, "uploads")
HASIL_DIR = os.path.join(TMP_DIR, "hasil_excel")
DB_PATH = os.path.join(TMP_DIR, "sindi.db")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(HASIL_DIR, exist_ok=True)


DB_PATH = "/tmp/sindi.db"
if not os.path.exists(DB_PATH):
    from create_db import create_database  # import fungsi yang kamu pakai
    create_database(DB_PATH)

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            parsed = urlparse(db_url)
            conn = psycopg2.connect(
                database=parsed.path[1:],
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname,
                port=parsed.port
            )
            print("✅ Connected to PostgreSQL")
            return conn
        except Exception as e:
            print(f"⚠️ PostgreSQL error: {e} — fallback to SQLite")

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------
# Auto-create database di Render jika belum ada
# -------------------------
def create_database(path):
    print(f"🧱 Membuat ulang database di {path} ...")
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT,
        role TEXT,
        kode_mdt TEXT,
        wilayah TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS pengajuan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_mdt TEXT,
        jenjang TEXT,
        tahun_pelajaran TEXT,
        jumlah_lulus INTEGER,
        file_lulusan TEXT,
        kabupaten TEXT,
        status TEXT,
        nomor_batch TEXT,
        alasan TEXT,
        tanggal_verifikasi TEXT,
        verifikator TEXT
    )
    """)
    conn.commit()
    conn.close()
    print("✅ Database siap digunakan.")

if not os.path.exists(DB_PATH):
    create_database(DB_PATH)

UPLOAD_DIR = "uploads"
ALLOWED_EXT = {"pdf", "xls", "xlsx"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# ==============================
#  INIT DATABASE (aman, idempotent)
# ==============================
def init_db():
    """Pastikan semua tabel dan kolom penting sudah ada."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        # 🔹 Pastikan kolom penting di pengajuan
        for col, tipe in [
            ("alasan", "TEXT"),
            ("kabupaten", "TEXT"),
            ("tanggal_verifikasi", "TEXT"),
            ("verifikator", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE pengajuan ADD COLUMN {col} {tipe}")
            except sqlite3.OperationalError:
                pass

        # 🔹 Buat tabel nomor_ijazah (kalau belum ada)
        c.execute("""
        CREATE TABLE IF NOT EXISTS nomor_ijazah (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pengajuan_id INTEGER,
            nama_santri TEXT,
            nis TEXT,
            nomor_ijazah TEXT,
            tahun TEXT,
            jenjang TEXT
        )
        """)

        # 🔹 Buat tabel riwayat_verifikasi (kalau belum ada)
        c.execute("""
        CREATE TABLE IF NOT EXISTS riwayat_verifikasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pengajuan_id INTEGER,
            nama_mdt TEXT,
            jenjang TEXT,
            tahun TEXT,
            jumlah_lulus INTEGER,
            status TEXT,
            alasan TEXT,
            verifikator TEXT,
            tanggal_verifikasi TEXT
        )
        """)

        conn.commit()
        print("✅ Semua tabel utama & riwayat_verifikasi sudah dicek/dibuat.")

def init_master_kabupaten():
    kabupaten_jabar = [
        ("Kabupaten Bandung", "Jawa Barat"), ("Kabupaten Bandung Barat", "Jawa Barat"),
        ("Kabupaten Bekasi", "Jawa Barat"), ("Kabupaten Bogor", "Jawa Barat"),
        ("Kabupaten Ciamis", "Jawa Barat"), ("Kabupaten Cianjur", "Jawa Barat"),
        ("Kabupaten Cirebon", "Jawa Barat"), ("Kabupaten Garut", "Jawa Barat"),
        ("Kabupaten Indramayu", "Jawa Barat"), ("Kabupaten Karawang", "Jawa Barat"),
        ("Kabupaten Kuningan", "Jawa Barat"), ("Kabupaten Majalengka", "Jawa Barat"),
        ("Kabupaten Pangandaran", "Jawa Barat"), ("Kabupaten Purwakarta", "Jawa Barat"),
        ("Kabupaten Subang", "Jawa Barat"), ("Kabupaten Sukabumi", "Jawa Barat"),
        ("Kabupaten Sumedang", "Jawa Barat"), ("Kabupaten Tasikmalaya", "Jawa Barat"),
        ("Kota Bandung", "Jawa Barat"), ("Kota Banjar", "Jawa Barat"),
        ("Kota Bekasi", "Jawa Barat"), ("Kota Bogor", "Jawa Barat"),
        ("Kota Cimahi", "Jawa Barat"), ("Kota Cirebon", "Jawa Barat"),
        ("Kota Depok", "Jawa Barat"), ("Kota Sukabumi", "Jawa Barat"),
        ("Kota Tasikmalaya", "Jawa Barat")
    ]
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS master_kabupaten (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_kabupaten TEXT NOT NULL UNIQUE,
            provinsi TEXT NOT NULL
        )
        """)
        c.executemany("""
            INSERT OR IGNORE INTO master_kabupaten (nama_kabupaten, provinsi)
            VALUES (?, ?)
        """, kabupaten_jabar)
        conn.commit()

def init_master_jenjang():
    jenjangs = [("Ula",), ("Wustha",), ("Ulya",), ("Al-Jami’ah",)]
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS master_jenjang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_jenjang TEXT NOT NULL UNIQUE
        )
        """)
        c.executemany("INSERT OR IGNORE INTO master_jenjang (nama_jenjang) VALUES (?)", jenjangs)
        conn.commit()

init_db()
init_master_kabupaten()
init_master_jenjang()

# ==============================
#  ROOTS
# ==============================
app.route("/preview/<path:filepath>")
def preview_file(filepath):
    import pandas as pd
    import os
    full_path = os.path.join(os.getcwd(), filepath)

    if not os.path.exists(full_path):
        return "<h4 class='text-danger p-3'>❌ File tidak ditemukan.</h4>"

    ext = filepath.split(".")[-1].lower()
    if ext in ["pdf"]:
        return f"<iframe src='/{filepath}' width='100%' height='600px'></iframe>"
    elif ext in ["xls", "xlsx"]:
        try:
            df = pd.read_excel(full_path)
            html_table = df.to_html(classes='table table-striped table-bordered table-hover', index=False)
            return f"""
            <div style='padding:10px'>
                <h5 class='text-success'>📄 Preview Excel: {os.path.basename(filepath)}</h5>
                <div style='overflow:auto; max-height:70vh;'>{html_table}</div>
            </div>
            """
        except Exception as e:
            return f"<p class='text-danger p-3'>Gagal membaca file Excel: {e}</p>"
    else:
        return f"<p class='text-muted p-3'>Format file {ext} belum didukung untuk pratinjau.</p>"

@app.route("/preview_upload/<path:filename>")
def preview_upload(filename):
    from urllib.parse import unquote
    import pandas as pd
    import os

    filename = unquote(filename)
    upload_path = os.path.join(os.getcwd(), "uploads", filename.replace("\\", "/"))

    if not os.path.exists(upload_path):
        return f"<h4 class='text-danger'>❌ File tidak ditemukan:<br>{upload_path}</h4>"

    try:
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        df = pd.read_excel(upload_path)
        df_html = df.to_html(classes="table table-bordered table-striped", index=False)
        return render_template("preview_excel.html", table_html=df_html, filename=filename)
    except Exception as e:
        return f"<h4 class='text-danger'>❌ Gagal membuka file Excel:<br>{e}</h4>"


@app.route("/")
def root():
    if not current_user():
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

# ==============================
#  AUTH
# ==============================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if login_user(request.form.get("username","").strip(), request.form.get("password","")):
            flash("Login berhasil.", "success")
            return redirect(url_for("dashboard"))
        flash("Username atau password salah.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    flash("Logout berhasil.", "info")
    return redirect(url_for("login"))

# ==============================
#  DASHBOARD
# ==============================
@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    data = {}

    with sqlite3.connect("sindi.db") as conn:
        c = conn.cursor()
        if user["role"] == "mdt":
            c.execute("SELECT COUNT(*), SUM(status='Ditetapkan'), SUM(status='Menunggu') FROM pengajuan WHERE mdt_id=?", (user["id"],))
            total, ditetapkan, menunggu = c.fetchone()
            data = {
                "pengajuan_total": total or 0,
                "ditetapkan": ditetapkan or 0,
                "menunggu": menunggu or 0
            }

        elif user["role"] == "kankemenag":
            c.execute("SELECT COUNT(*), SUM(status='Menunggu'), SUM(status='Diverifikasi') FROM pengajuan")
            total, menunggu, diverifikasi = c.fetchone()
            data = {
                "total": total or 0,
                "menunggu": menunggu or 0,
                "diverifikasi": diverifikasi or 0
            }

        elif user["role"] == "kanwil":
            c.execute("SELECT COUNT(*), SUM(status='Ditetapkan') FROM pengajuan WHERE status IN ('Diverifikasi','Ditetapkan')")
            total, ditetapkan = c.fetchone()
            c.execute("SELECT COUNT(*) FROM nomor_ijazah")
            total_santri = c.fetchone()[0]

            total = total or 0
            ditetapkan = ditetapkan or 0
            data = {
                "total": total,
                "ditetapkan": ditetapkan,
                "total_santri": total_santri or 0,
                "menunggu": 0,
                "diverifikasi": total - ditetapkan if total and ditetapkan is not None else 0
            }

    return render_template("dashboard.html", user=user, data=data)

# ==============================
#  MDT: Pengajuan Batch + Upload Excel/PDF
# ==============================
@app.route("/pengajuan", methods=["GET", "POST"])
@require_role("mdt")
def pengajuan_mdt():
    from services.mdt_service import list_kabupaten
    user = current_user()

    # --- Ambil data dropdown dari database ---
    kabupaten_list = list_kabupaten()

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT nama_jenjang FROM master_jenjang ORDER BY id ASC")
        jenjang_list = [r[0] for r in c.fetchall()]

    # --- Jika form dikirim (POST) ---
    if request.method == "POST":
        nama_mdt = (request.form.get("nama_mdt") or user["kode_mdt"] or "MDT").strip()
        jenjang = (request.form.get("jenjang") or "").strip()
        tahun = (request.form.get("tahun_pelajaran") or "").strip()
        jumlah = (request.form.get("jumlah_lulus") or "0").strip()
        kabupaten = (request.form.get("kabupaten") or "").strip()

        file = request.files.get("file_lulusan")
        if not file or file.filename == "":
            flash("File daftar lulusan wajib diunggah (PDF/Excel).", "warning")
            return redirect(url_for("pengajuan_mdt"))

        if not allowed_file(file.filename):
            flash("Format file harus PDF/XLS/XLSX.", "danger")
            return redirect(url_for("pengajuan_mdt"))

        filename = f"{user['kode_mdt']}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        # Buat batch baru
        nomor_batch = create_pengajuan_batch(
            mdt_user=user,
            nama_mdt=nama_mdt,
            jenjang=jenjang,
            tahun_pelajaran=tahun,
            jumlah_lulus=jumlah,
            file_lulusan_path=save_path
        )

        # Simpan kabupaten di pengajuan
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("UPDATE pengajuan SET kabupaten=? WHERE nomor_batch=?", (kabupaten, nomor_batch))
            conn.commit()

        flash(f"✅ Pengajuan terkirim. Nomor Batch: {nomor_batch}", "success")
        return redirect(url_for("pengajuan_mdt"))

    # --- Ambil daftar pengajuan yang sudah dikirim oleh MDT ini ---
    pengajuans = list_pengajuan_batch_by_mdt(user["id"])

    # --- Kirim semua data ke template ---
    return render_template(
        "pengajuan.html",
        user=user,
        pengajuans=pengajuans,
        kabupaten_list=kabupaten_list,
        jenjang_list=jenjang_list
    )

@app.route("/hasil_mdt")
@require_role("mdt")
def hasil_mdt():
    from services.mdt_service import list_hasil_penetapan
    user = current_user()

    hasil_list = list_hasil_penetapan(kode_mdt=user["kode_mdt"])
    return render_template("hasil_mdt.html", user=user, hasil_list=hasil_list)

@app.route("/hasil_kanwil")
@require_role(["kanwil", "admin"])
def hasil_kanwil():
    from services.mdt_service import list_hasil_penetapan
    user = current_user()

    kabupaten_dipilih = request.args.get("kabupaten", "")
    jenjang_dipilih = request.args.get("jenjang", "")

    hasil_list = list_hasil_penetapan(kabupaten=kabupaten_dipilih or None, jenjang=jenjang_dipilih or None)

    daftar_kabupaten = sorted({row["kabupaten"] for row in hasil_list if row["kabupaten"]})
    daftar_jenjang = sorted({row["jenjang"] for row in hasil_list if row["jenjang"]})

    return render_template(
        "hasil_kanwil.html",
        user=user,
        hasil_list=hasil_list,
        daftar_kabupaten=daftar_kabupaten,
        daftar_jenjang=daftar_jenjang,
        kabupaten_dipilih=kabupaten_dipilih,
        jenjang_dipilih=jenjang_dipilih
    )

# ==============================
#  KANKEMENAG: Verifikasi (unggah rekomendasi)
# ==============================
@app.route("/verifikasi", methods=["GET", "POST"])
@require_role("kankemenag")
def verifikasi_kemenag():
    from services.mdt_service import list_pengajuan_for_kemenag, update_status_pengajuan, list_riwayat_verifikasi_kemenag
    user = current_user()

    if request.method == "POST":
        pengajuan_id = request.form.get("pengajuan_id")
        status = request.form.get("status")
        alasan = request.form.get("alasan", "").strip() or None

        update_status_pengajuan(pengajuan_id, status, alasan, user["username"])
        flash(f"✅ Pengajuan berhasil diperbarui sebagai {status}.", "success")
        return redirect(url_for("verifikasi_kemenag"))

    pengajuan_list = list_pengajuan_for_kemenag()
    riwayat_list = list_riwayat_verifikasi_kemenag()
    return render_template("verifikasi.html", user=user, pengajuan_list=pengajuan_list, riwayat_list=riwayat_list)


@app.route("/riwayat_verifikasi")
@require_role("kankemenag")
def riwayat_verifikasi():
    from services.mdt_service import list_riwayat_verifikasi_kemenag
    user = current_user()
    riwayat_list = list_riwayat_verifikasi_kemenag()
    return render_template("riwayat_verifikasi.html", user=user, riwayat_list=riwayat_list)

# ==============================
#  KANWIL: Penetapan + Export (Excel/PDF)
# ==============================
@app.route("/penetapan", methods=["GET", "POST"])
@require_role(["kanwil", "admin"])
def penetapan_kanwil():
    from services.mdt_service import list_pengajuan_for_kanwil, tetapkan_pengajuan, list_kabupaten

    if request.method == "POST":
        pengajuan_id = request.form.get("pengajuan_id")
        tetapkan_pengajuan(pengajuan_id)
        flash("✅ Nomor Ijazah berhasil ditetapkan.", "success")
        return redirect(url_for("penetapan_kanwil"))

    kab_filter = request.args.get("kabupaten")
    jenjang_filter = request.args.get("jenjang")

    query = """
        SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus,
               file_lulusan, status, kabupaten, alasan, verifikator, tanggal_verifikasi
        FROM pengajuan
        WHERE status = 'Diverifikasi'
    """
    params = []

    if kab_filter:
        query += " AND kabupaten=?"
        params.append(kab_filter)
    if jenjang_filter:
        query += " AND jenjang=?"
        params.append(jenjang_filter)

    query += " ORDER BY id DESC"

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(query, params)
        pengajuan_list = c.fetchall()

    daftar_kabupaten = [(i+1, k) for i, k in enumerate(list_kabupaten())]
    return render_template("penetapan.html",
                           user=current_user(),
                           pengajuan_list=pengajuan_list,
                           daftar_kabupaten=daftar_kabupaten)

@app.route("/hasil/download/<path:filename>")
def download_hasil(filename):
    from flask import send_from_directory
    hasil_dir = os.path.join(os.getcwd(), "hasil_excel")
    return send_from_directory(hasil_dir, filename, as_attachment=True)

@app.route("/penetapan/export/<string:mode>/<int:pengajuan_id>")
@require_role("kanwil")
def export_penetapan(mode, pengajuan_id):
    filename = f"hasil_penetapan_{pengajuan_id}"
    try:
        if mode == "excel":
            file_path = os.path.join(UPLOAD_DIR, f"{filename}.xlsx")
            export_nomor_ijazah_excel(pengajuan_id, file_path)
        elif mode == "pdf":
            file_path = os.path.join(UPLOAD_DIR, f"{filename}.pdf")
            export_nomor_ijazah_pdf(pengajuan_id, file_path)
        else:
            flash("Format export tidak valid.", "danger")
            return redirect(url_for("penetapan_kanwil"))

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        flash(f"❌ Gagal export data: {e}", "danger")
        return redirect(url_for("penetapan_kanwil"))

# ==============================
#  MDT: Lihat Hasil Penetapan
# ==============================
@app.route("/hasil")
@require_role(["mdt", "kanwil"])
def hasil():
    from services.mdt_service import get_nomor_ijazah_by_pengajuan
    user = current_user()

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()

        if user["role"] == "mdt":
            c.execute("""
                SELECT id, nomor_batch, nama_mdt, status, tahun_pelajaran, jenjang
                FROM pengajuan WHERE mdt_id=? AND status='Ditetapkan' ORDER BY id DESC
            """, (user["id"],))
        else:  # Kanwil
            c.execute("""
                SELECT id, nomor_batch, nama_mdt, status, tahun_pelajaran, jenjang
                FROM pengajuan WHERE status='Ditetapkan' ORDER BY id DESC
            """)

        pengajuan_list = c.fetchall()

    results = []
    for p in pengajuan_list:
        data = get_nomor_ijazah_by_pengajuan(p[0])
        if data:
            results.append((p, data))

    return render_template("hasil.html", user=user, results=results)
    
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.isfile(filepath):
        return f"<h4 class='text-danger'>❌ File tidak ditemukan: {filepath}</h4>", 404
    return send_file(filepath, as_attachment=False)


def list_hasil_penetapan(kode_mdt=None, kabupaten=None, jenjang=None):
    conn = conn()
    c = conn.cursor()
    query = """
        SELECT 
            p.id, p.nama_mdt, p.jenjang, p.tahun_pelajaran, 
            p.jumlah_lulus, p.kabupaten, p.nomor_batch, 
            COALESCE(p.file_hasil, p.file_lulusan) AS file_path
        FROM pengajuan p
        WHERE p.status = 'Ditetapkan'
        ORDER BY p.id DESC
    """
    c.execute(query)
    rows = c.fetchall()
    conn.close()

    hasil = []
    for r in rows:
        hasil.append({
            "id": r[0],
            "nama_mdt": r[1],
            "jenjang": r[2],
            "tahun": r[3],
            "jumlah": r[4],
            "kabupaten": r[5],
            "batch": r[6],
            "file_path": r[7] or ""
        })
    return hasil

@app.route("/uploads/<filename>")
def uploads(filename):
    filepath = os.path.join("/tmp/uploads", filename)
    if not os.path.exists(filepath):
        return f"<h4 class='text-danger'>❌ File tidak ditemukan: {filepath}</h4>", 404
    return send_file(filepath, as_attachment=False)


@app.route("/hasil_excel/<path:filename>")
def hasil_excel(filename):
    filepath = os.path.join(HASIL_DIR, filename)
    if not os.path.isfile(filepath):
        return f"<h4 class='text-danger'>❌ File tidak ditemukan: {filepath}</h4>", 404
    return send_file(filepath, as_attachment=False)

@app.route("/preview-file/<path:filename>")
def preview_file(filename):
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    file_path = os.path.join(uploads_dir, filename)

    print(f"🔍 Preview request for: {file_path}")  # <-- Tambahkan ini di sini

    if not os.path.isfile(file_path):
        print("❌ File tidak ditemukan.")
        return "<div class='alert alert-danger p-3'>❌ File tidak ditemukan.</div>"

    ext = filename.split(".")[-1].lower()

    # ✅ Jika Excel: render ke tabel HTML
    if ext in ["xlsx", "xls"]:
        try:
            df = pd.read_excel(file_path)
            html_table = df.to_html(
                index=False,
                classes="table table-bordered table-striped table-sm align-middle",
                border=0
            )
            return render_template("lihat_file_modal.html", filename=filename, table_html=html_table)
        except Exception as e:
            return f"<div class='alert alert-danger p-3'>Gagal membaca Excel: {e}</div>"

    # ✅ Jika PDF: tampil langsung dalam iframe
    elif ext == "pdf":
        return f"<iframe src='/uploads/{filename}' width='100%' height='600px' style='border:none;'></iframe>"

    # ❌ File lain: beri opsi download
    else:
        return f"""
        <div class='p-5 text-center text-muted'>
            <i class='bi bi-exclamation-triangle display-4'></i>
            <p>Format file <b>.{ext}</b> tidak bisa dipratinjau.<br>
            <a href='/uploads/{filename}' download class='btn btn-success mt-3'>
                <i class='bi bi-download'></i> Unduh File Asli
            </a></p>
        </div>
        """
        
@app.route("/preview_excel/<path:filename>")
def preview_excel(filename):
    from urllib.parse import unquote
    import pandas as pd

    filename = unquote(filename)
    hasil_dir = os.path.join(os.getcwd(), "hasil_excel")
    uploads_dir = os.path.join(os.getcwd(), "uploads")

    hasil_path = os.path.join(hasil_dir, filename)
    upload_path = os.path.join(uploads_dir, filename)

    if os.path.exists(hasil_path):
        file_path = hasil_path
    elif os.path.exists(upload_path):
        file_path = upload_path
    else:
        return f"<h4 class='text-danger'>❌ File tidak ditemukan:<br>{filename}</h4>"

    df = pd.read_excel(file_path)
    df_html = df.to_html(classes="table table-bordered table-striped", index=False)
    return render_template("preview_excel.html", table_html=df_html, filename=filename)


# ==============================
#  ADMIN
# ==============================

@app.route("/admin/users", methods=["GET", "POST"])
@require_role(["kanwil", "admin"])
def admin_users():
    import math

    # === FORM SUBMIT TAMBAH USER ===
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip() or "123"
        role = request.form.get("role", "").strip()
        kode_mdt = request.form.get("kode_mdt", "").strip() or None
        wilayah = request.form.get("wilayah", "").strip() or None

        ok, msg = create_user(username, password, role, kode_mdt, wilayah)
        flash(msg, "success" if ok else "danger")
        return redirect(url_for("admin_users"))

    # === PAGINATION ===
    page = int(request.args.get("page", 1))
    per_page = 50  # tampilkan 50 user per halaman
    offset = (page - 1) * per_page

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # total data
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]

    # ambil hanya data di halaman ini
    c.execute("""
        SELECT id, username, password, role, kode_mdt, wilayah
        FROM users
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    users = c.fetchall()
    conn.close()

    total_pages = math.ceil(total / per_page)

    return render_template(
        "users.html",
        users=users,
        user=current_user(),
        page=page,
        total_pages=total_pages,
        total=total
    )

@app.route("/admin/log")
@require_role("admin")
def admin_log():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # pastikan tabel log_aktivitas ada
    c.execute("""
    CREATE TABLE IF NOT EXISTS log_aktivitas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        aksi TEXT,
        waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # ambil data log terbaru
    c.execute("SELECT username, aksi, waktu FROM log_aktivitas ORDER BY waktu DESC LIMIT 200")
    data = c.fetchall()
    conn.close()
    
    return render_template("admin_log.html", user=current_user(), log_list=data)

@app.route("/admin/kabupaten", methods=["GET", "POST"])
@require_role("admin")
def admin_kabupaten():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    if request.method == "POST":
        nama_kabupaten = request.form.get("nama_kabupaten").strip()
        provinsi = "Jawa Barat"
        if nama_kabupaten:
            c.execute("""
                INSERT OR IGNORE INTO master_kabupaten (nama_kabupaten, provinsi)
                VALUES (?, ?)
            """, (nama_kabupaten, provinsi))
            conn.commit()
            flash("✅ Kabupaten/Kota berhasil ditambahkan.", "success")
        else:
            flash("⚠️ Nama kabupaten/kota tidak boleh kosong.", "warning")

    c.execute("SELECT * FROM master_kabupaten ORDER BY nama_kabupaten ASC")
    data = c.fetchall()
    conn.close()
    return render_template("admin_kabupaten.html", user=current_user(), data=data)

# ==============================
#  ADMIN - RESET PASSWORD USER
# ==============================
@app.route("/admin/reset-password/<int:user_id>", methods=["POST"])
@require_role(["admin", "kanwil"])
def reset_password(user_id):
    import sqlite3

    new_password = "123"  # default reset password
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE users SET password=? WHERE id=?", (new_password, user_id))
        conn.commit()

        # ambil username untuk log
        c.execute("SELECT username FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        username = row[0] if row else "tidak diketahui"

    # catat aktivitas reset password
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO log_aktivitas (username, aksi)
                VALUES (?, ?)
            """, (current_user()["username"], f"Reset password untuk user '{username}'"))
            conn.commit()
    except:
        pass  # biar tidak crash kalau tabel log belum ada

    flash(f"🔑 Password user '{username}' telah direset ke default (123).", "info")
    return redirect(url_for("admin_users"))

@app.route("/hasil")
@require_role(["mdt", "kanwil"])
def hasil_view():
    from services.mdt_service import list_hasil_penetapan_by_role
    user = current_user()
    hasil = list_hasil_penetapan_by_role(user["role"])
    return render_template("hasil.html", user=user, hasil=hasil)

import logging
from logging import StreamHandler

handler = StreamHandler()
handler.setLevel(logging.DEBUG)
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)


# ==============================
#  RUN
# ==============================
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

# biar bisa dikenali Render
if __name__ == "app_gateway":
    app = app
