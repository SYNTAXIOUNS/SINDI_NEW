# 🕌 SINDI - Sistem Penomoran Ijazah MDT

Aplikasi berbasis Flask untuk pengelolaan dan verifikasi nomor ijazah MDT oleh Kemenag.

## 🚀 Fitur
- Login multi-role (MDT, Kankemenag, Kanwil)
- Upload dan verifikasi dokumen (Excel/PDF)
- Pratinjau file langsung di modal
- Statistik Dashboard dinamis
- Database SQLite dengan schema modular

## 🛠️ Instalasi
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python init_db.py
flask run
