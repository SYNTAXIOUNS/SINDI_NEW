from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3, os, datetime
from werkzeug.utils import secure_filename

# ====== SERVICES (pastikan fungsi-fungsi ini ada di services/*.py) ======
from services.auth_service import login_user, logout_user, current_user, require_role
from services.admin_service import list_users, create_user
from services.mdt_service import (
    _conn,  # helper koneksi
    # MDT (batch pengajuan)
    create_pengajuan_batch, list_pengajuan_batch_by_mdt,
    # Kankemenag (verifikasi)
    list_pengajuan_for_kemenag, update_status_to_diverifikasi,
    # Kanwil (penetapan + export)
    list_pengajuan_for_kanwil, generate_nomor_ijazah_batch,
    export_nomor_ijazah_excel, export_nomor_ijazah_pdf,
    # MDT (hasil)
    get_nomor_ijazah_by_pengajuan,
)
from flask import send_file, jsonify
from flask import send_from_directory, abort
import os
from flask import render_template
import pandas as pd
from urllib.parse import unquote

# ====== APP CONFIG ======
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "sindi_secret_key_please_change"
DB_NAME = r"D:/Pribados/Project/SINDI/sindi.db"


UPLOAD_DIR = "uploads"
ALLOWED_EXT = {"pdf", "xls", "xlsx"}
os.makedirs(UPLOAD_DIR, exist_ok=True)

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

# ==============================
#  INIT DATABASE (aman, idempotent)
# ==============================
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        # users
        c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            kode_mdt TEXT,
            wilayah TEXT
        )
        """)
        # pengajuan (batch MDT)
        c.execute("""
        CREATE TABLE IF NOT EXISTS pengajuan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_mdt TEXT,
            jenjang TEXT,
            tahun_pelajaran TEXT,
            jumlah_lulus INTEGER,
            file_lulusan TEXT,
            tanggal_pengajuan TEXT,
            status TEXT,
            nomor_batch TEXT,
            rekomendasi_file TEXT,
            mdt_id INTEGER,
            FOREIGN KEY (mdt_id) REFERENCES users (id)
        )
        """)
        # nomor_ijazah (hasil penetapan per-santri)
        c.execute("""
        CREATE TABLE IF NOT EXISTS nomor_ijazah (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pengajuan_id INTEGER,
            nama_santri TEXT,
            nis TEXT,
            nomor_ijazah TEXT,
            tahun TEXT,
            jenjang TEXT,
            FOREIGN KEY (pengajuan_id) REFERENCES pengajuan (id)
        )
        """)
        # seed users (idempotent)
        users = [
            ("mdt", "123", "mdt", "MDT001", "Kota Cimahi"),
            ("kemenag", "123", "kankemenag", None, "Kota Cimahi"),
            ("kanwil", "123", "kanwil", None, "Jawa Barat"),
            ("admin", "123", "admin", None, "Kanwil Jabar"),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO users (username, password, role, kode_mdt, wilayah) VALUES (?, ?, ?, ?, ?)",
            users
        )
        conn.commit()

init_db()

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
    user = current_user()
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM master_kabupaten ORDER BY nama_kabupaten ASC")
    daftar_kabupaten = c.fetchall()
    conn.close()

    if request.method == "POST":
        nama_mdt = (request.form.get("nama_mdt") or user["kode_mdt"]).strip()
        kabupaten = request.form.get("kabupaten")
        jenjang = request.form.get("jenjang")
        tahun = request.form.get("tahun_pelajaran")
        jumlah = request.form.get("jumlah_lulus")
        file = request.files.get("file_lulusan")

        if not file or file.filename == "":
            flash("File daftar lulusan wajib diunggah (PDF/Excel).", "warning")
            return redirect(url_for("pengajuan_mdt"))

        filename = f"{user['kode_mdt']}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(file.filename)}"
        save_path = os.path.join(UPLOAD_DIR, filename)
        file.save(save_path)

        nomor_batch = create_pengajuan_batch(
            mdt_user=user,
            nama_mdt=nama_mdt,
            jenjang=jenjang,
            tahun_pelajaran=tahun,
            jumlah_lulus=jumlah,
            file_lulusan_path=save_path
        )

        # Simpan kabupaten juga
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("UPDATE pengajuan SET kabupaten=? WHERE nomor_batch=?", (kabupaten, nomor_batch))
            conn.commit()

        flash(f"Pengajuan terkirim. Nomor Batch: {nomor_batch}", "success")
        return redirect(url_for("pengajuan_mdt"))

    pengajuans = list_pengajuan_batch_by_mdt(user["id"])
    return render_template("pengajuan.html", user=user, pengajuans=pengajuans, daftar_kabupaten=daftar_kabupaten)

@app.route("/hasil_mdt")
@require_role("mdt")
def hasil_mdt():
    """
    Halaman MDT untuk melihat hasil penetapan nomor ijazah mereka sendiri.
    File diambil dari folder hasil_excel/ berdasarkan kode MDT pengguna.
    """
    import os
    from flask import render_template
    user = current_user()

    hasil_dir = os.path.join(os.getcwd(), "hasil_excel")
    hasil_list = []

    if os.path.exists(hasil_dir):
        for f in os.listdir(hasil_dir):
            if user["kode_mdt"] in f:  # contoh: HASIL_MDT001_2024_Ula.xlsx
                # parsing nama file: HASIL_<kode>_<tahun>_<jenjang>.xlsx
                parts = f.replace(".xlsx", "").split("_")
                tahun = parts[2] if len(parts) > 2 else "-"
                jenjang = parts[3] if len(parts) > 3 else "-"
                hasil_list.append({
                    "file_name": f,
                    "file_path": f"hasil_excel/{f}",
                    "jenjang": jenjang,
                    "tahun": tahun
                })

    return render_template("hasil_mdt.html", user=user, hasil_list=hasil_list)

@app.route("/hasil_kanwil")
@require_role("kanwil", "admin")
def hasil_kanwil():
    from services.mdt_service import list_hasil_penetapan
    from services.auth_service import current_user

    kabupaten_dipilih = request.args.get("kabupaten", "")
    jenjang_dipilih = request.args.get("jenjang", "")

    # Ambil semua data hasil penetapan dari service
    hasil_list = list_hasil_penetapan()

    # Tambahkan kolom kabupaten fallback bila belum ada
    for h in hasil_list:
        if "kabupaten" not in h:
            h["kabupaten"] = h.get("wilayah", "Tidak diketahui")

    # Filter berdasarkan kabupaten & jenjang
    if kabupaten_dipilih:
        hasil_list = [h for h in hasil_list if h.get("kabupaten") == kabupaten_dipilih]
    if jenjang_dipilih:
        hasil_list = [h for h in hasil_list if h.get("jenjang") == jenjang_dipilih]

    # Daftar dropdown unik
    semua_data = list_hasil_penetapan()
    daftar_kabupaten = sorted(list({h.get("kabupaten") for h in semua_data}))
    daftar_jenjang = sorted(list({h.get("jenjang") for h in semua_data}))

    return render_template(
        "hasil_kanwil.html",
        user=current_user(),  # ✅ fix utama agar tidak undefined
        hasil_list=hasil_list,
        daftar_kabupaten=daftar_kabupaten,
        daftar_jenjang=daftar_jenjang,
        kabupaten_dipilih=kabupaten_dipilih,
        jenjang_dipilih=jenjang_dipilih,
    )

# ==============================
#  KANKEMENAG: Verifikasi (unggah rekomendasi)
# ==============================
@app.route("/verifikasi", methods=["GET", "POST"])
@require_role("kankemenag")
def verifikasi_kemenag():
    from services.mdt_service import list_pengajuan_for_kemenag, update_status_pengajuan
    user = current_user()

    if request.method == "POST":
        pengajuan_id = request.form.get("pengajuan_id")
        status = request.form.get("status")
        alasan = request.form.get("alasan", "").strip() or None

        update_status_pengajuan(pengajuan_id, status, alasan)
        flash(f"✅ Pengajuan berhasil diperbarui sebagai {status}.", "success")
        return redirect(url_for("verifikasi_kemenag"))

    pengajuan_list = list_pengajuan_for_kemenag()
    return render_template("verifikasi.html", user=user, pengajuan_list=pengajuan_list)

# ==============================
#  KANWIL: Penetapan + Export (Excel/PDF)
# ==============================
@app.route("/penetapan", methods=["GET", "POST"])
@require_role("kanwil","admin")
def penetapan_kanwil():
    user = current_user()
    kab_filter = request.args.get("kabupaten")
    jenjang_filter = request.args.get("jenjang")

    query = "SELECT * FROM pengajuan WHERE status='Diverifikasi'"
    params = []

    if kab_filter:
        query += " AND kabupaten=?"
        params.append(kab_filter)
    if jenjang_filter:
        query += " AND jenjang=?"
        params.append(jenjang_filter)

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(query, params)
        pengajuan_list = c.fetchall()

        c.execute("SELECT * FROM master_kabupaten ORDER BY nama_kabupaten ASC")
        daftar_kabupaten = c.fetchall()

    return render_template("penetapan.html", user=user, pengajuan_list=pengajuan_list, daftar_kabupaten=daftar_kabupaten)

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


# ==============================
#  ADMIN KANWIL: Manajemen User
# ==============================
@app.route("/admin/users", methods=["GET","POST"])
@require_role("kanwil")
def admin_users():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip() or "123"
        role     = request.form.get("role","").strip()
        kode_mdt = request.form.get("kode_mdt","").strip() or None
        wilayah  = request.form.get("wilayah","").strip() or None
        ok, msg = create_user(username, password, role, kode_mdt, wilayah)
        flash(msg, "success" if ok else "danger")
        return redirect(url_for("admin_users"))
    users = list_users()
    return render_template("users.html", users=users, user=current_user())

def list_pengajuan_for_kemenag():
    """Ambil daftar pengajuan yang belum diverifikasi"""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, nomor_batch, nama_mdt, jenjang, tahun_pelajaran, jumlah_lulus, 
                   file_lulusan, created_at, status
            FROM pengajuan
            WHERE status IS NULL OR status='Diajukan'
            ORDER BY created_at DESC
        """)
        return c.fetchall()
    
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    """
    Melayani file dari folder /uploads agar bisa dipratinjau langsung di browser (PDF, XLSX, dsb)
    """
    uploads_dir = os.path.join(os.getcwd(), "uploads")
    
    # Normalisasi path agar aman (hindari traversal ../../)
    safe_path = os.path.normpath(os.path.join(uploads_dir, filename))
    
    # Cegah akses di luar folder uploads
    if not safe_path.startswith(uploads_dir):
        abort(403)
    
    # Pastikan file ada
    if not os.path.isfile(safe_path):
        abort(404)
    
    # Kirim file
    return send_from_directory(uploads_dir, filename, as_attachment=False)

# =============================================
# Serve folder hasil_excel (untuk file hasil ijazah)
# =============================================
@app.route("/hasil_excel/<path:filename>")
def serve_hasil_excel(filename):
    import os
    from flask import send_from_directory, abort

    hasil_dir = os.path.join(os.getcwd(), "hasil_excel")
    file_path = os.path.join(hasil_dir, filename)

    if not os.path.exists(file_path):
        abort(404)

    return send_from_directory(hasil_dir, filename, as_attachment=False)

# ======================================================
# ✅ Preview file Excel hasil penetapan ijazah (langsung dibaca)
# ======================================================
from urllib.parse import unquote
import os
import pandas as pd
from flask import render_template

@app.route("/preview_excel/<path:filename>")
def preview_excel(filename):
    filename = unquote(filename)  # decode karakter khusus seperti spasi, tanda petik, dll

    # 🔹 Ganti direktori ke folder hasil_excel
    hasil_dir = os.path.join(os.getcwd(), "hasil_excel")
    file_path = os.path.join(hasil_dir, filename)

    if not os.path.exists(file_path):
        return f"<h4 class='text-danger'>❌ File tidak ditemukan: {file_path}</h4>"

    try:
        # tampilkan semua baris dan kolom
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)

        df = pd.read_excel(file_path)
        df_html = df.to_html(classes="table table-bordered table-striped", index=False)

        return render_template("preview_excel.html", table_html=df_html, filename=filename)
    except Exception as e:
        return f"<h4 class='text-danger'>❌ Gagal memuat file Excel:<br>{e}</h4>"

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
# ==============================
#  ADMIN
# ==============================

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
#  RUN
# ==============================
if __name__ == "__main__":
    app.run(debug=True)
