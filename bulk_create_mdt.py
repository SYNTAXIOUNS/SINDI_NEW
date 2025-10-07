#!/usr/bin/env python3
"""
bulk_create_mdt.py

Buat akun MDT massal dari Excel. Password = nama_lembaga (dihapus char non-alfanumerik) + "1!"

Contoh:
    python bulk_create_mdt.py --input "Lembaga_MDT.xlsx" --out "mdt_accounts.csv"

Opsi:
  --input         path ke file excel (.xls/.xlsx) (wajib)
  --sheet         sheet name (opsional)
  --db            sqlite db path (default: sindi.db)
  --out           output CSV (default accounts_created_<input>.csv)
  --name-col      nama kolom yang berisi nama MDT (kalau tidak terdeteksi)
  --kode-col      kolom kode MDT (opsional)
  --wilayah-col   kolom wilayah (opsional)
  --hash-password (tidak aktif oleh default; script menyimpan plain password)
"""
import argparse
import sqlite3
import os
import pandas as pd
import random
import string
from pathlib import Path

DEFAULT_DB = "sindi.db"

def slugify(name: str):
    s = "".join(ch for ch in name.lower().strip() if ch.isalnum() or ch in (" ", "-", "_"))
    return "_".join(s.split())

def normalize_password_from_name(name: str):
    # Hapus karakter non-alfanumerik, lalu tambahkan "1!"
    clean = "".join(ch for ch in name if ch.isalnum())
    if not clean:
        # fallback random if name becomes empty
        clean = "mdt"
    return f"{clean}1!"

def ensure_db_tables(conn):
    c = conn.cursor()
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
    conn.commit()

def read_excel(path, sheet_name=None):
    if sheet_name:
        df = pd.read_excel(path, sheet_name=sheet_name)
    else:
        df = pd.read_excel(path)
    return df

def main(args):
    infile = Path(args.input)
    if not infile.exists():
        print(f"ERROR: File input tidak ditemukan: {infile}")
        return

    df = read_excel(infile, args.sheet)
    print(f"Loaded {len(df)} rows from Excel.")

    # detect columns
    name_col = args.name_col or next((c for c in df.columns if "nama" in c.lower() or "lembaga" in c.lower()), None)
    kode_col = args.kode_col or next((c for c in df.columns if "kode" in c.lower() or "kd" in c.lower()), None)
    wilayah_col = args.wilayah_col or next((c for c in df.columns if "wilayah" in c.lower() or "kota" in c.lower() or "kab" in c.lower()), None)

    print("Detected columns:")
    print(f"  name_col    = {name_col}")
    print(f"  kode_col    = {kode_col}")
    print(f"  wilayah_col = {wilayah_col}")

    if not name_col:
        print("ERROR: Tidak dapat mendeteksi kolom nama MDT. Gunakan --name-col untuk menentukan.")
        return

    # prepare DB
    conn = sqlite3.connect(args.db)
    ensure_db_tables(conn)
    c = conn.cursor()

    created = []
    skipped = []

    for idx, row in df.iterrows():
        nama = str(row.get(name_col)).strip() if pd.notna(row.get(name_col)) else ""
        if not nama or nama.lower() in ("nan", "none"):
            skipped.append((idx, "nama kosong"))
            continue

        kode = str(row.get(kode_col)).strip() if kode_col and pd.notna(row.get(kode_col)) else ""
        wilayah = str(row.get(wilayah_col)).strip() if wilayah_col and pd.notna(row.get(wilayah_col)) else None

        # username: prefer kode jika ada, else slug nama, ensure unique by suffix numeric if needed
        base_username = kode if kode else slugify(nama)
        username = base_username
        counter = 1
        while True:
            c.execute("SELECT id FROM users WHERE username=?", (username,))
            if c.fetchone():
                username = f"{base_username}{counter}"
                counter += 1
            else:
                break

        # password per permintaan: dari nama lembaga + "1!" (non-alfanumerik dihapus)
        password = normalize_password_from_name(nama)

        # store plain password (app saat ini memakai plain). If you want to hash,
        # enable hashing and update auth_service login logic accordingly.
        stored_password = password

        role = "mdt"
        kode_mdt = kode if kode else None

        # Insert, ignore duplicates
        try:
            c.execute("""
                INSERT INTO users (username, password, role, kode_mdt, wilayah)
                VALUES (?, ?, ?, ?, ?)
            """, (username, stored_password, role, kode_mdt, wilayah))
            conn.commit()
            created.append({
                "username": username,
                "password": password,
                "nama_mdt": nama,
                "kode_mdt": kode_mdt,
                "wilayah": wilayah
            })
            print(f"[CREATED] {username}  (MDT: {nama})")
        except sqlite3.IntegrityError:
            skipped.append((idx, "username exists"))
            print(f"[SKIP] username exists: {username}")

    conn.close()

    out_path = Path(args.out or f"accounts_created_{infile.stem}.csv")
    df_out = pd.DataFrame(created)
    if not df_out.empty:
        df_out.to_csv(out_path, index=False)
        print(f"\n✅ Created {len(created)} accounts. CSV saved to: {out_path}")
    else:
        print("\nℹ️ No accounts created.")

    if skipped:
        print(f"Skipped rows: {len(skipped)} (sample): {skipped[:10]}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to input Excel file (.xls/.xlsx)")
    parser.add_argument("--sheet", required=False, help="Sheet name (optional)")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to sqlite DB (default sindi.db)")
    parser.add_argument("--out", help="Output CSV file (default accounts_created_<input>.csv)")
    parser.add_argument("--name-col", dest="name_col", help="Column name for nama MDT (optional)")
    parser.add_argument("--kode-col", dest="kode_col", help="Column name for kode MDT (optional)")
    parser.add_argument("--wilayah-col", dest="wilayah_col", help="Column name for wilayah (optional)")
    args = parser.parse_args()
    main(args)
