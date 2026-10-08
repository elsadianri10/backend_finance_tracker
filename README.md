# Backend Finance Tracker

Backend FastAPI untuk pengelolaan keuangan pribadi. Tahap pertama: Sign in with Google, akun pengguna, dan access token JWT aplikasi. Database: PostgreSQL dengan SQLAlchemy async / asyncpg.

## Menjalankan lokal

1. Gunakan Python 3.12+ dan PostgreSQL yang sudah berjalan.
2. Buat virtual environment bila belum tersedia, lalu install dependency:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Salin `.env.example` menjadi `.env` jika belum ada. Jika memakai `.env` dari template lama, sesuaikan DB ke PostgreSQL (`DB_PORT=5432`, `DATABASE_NAME=finance_tracker`) dan ubah `ORIGINS` menjadi daftar dipisah koma atau JSON satu baris. `.env` lama tidak diubah otomatis.
4. Isi `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DATABASE_NAME`, `GOOGLE_CLIENT_ID`, dan `SECRET_KEY`. Buat secret acak:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

5. Buat database dan jalankan baseline sekali:

```powershell
createdb -h localhost -p 5432 -U postgres finance_tracker
psql -h localhost -p 5432 -U postgres -d finance_tracker -v ON_ERROR_STOP=1 -f database/000_init.sql
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Swagger: http://localhost:8000/docs. Struktur SQL dan aturan penomoran: [database/README.md](database/README.md).

Untuk PostgreSQL hosted seperti Neon, isi parameter `DB_*` dari provider dan set `DB_SSL=true` di environment deployment. Koneksi memakai TLS dengan verifikasi sertifikat dan hostname. Gunakan `ENCRYPTION_KEY` lokal yang sama jika database deployment merupakan salinan data lokal; jangan menjalankan baseline reset setelah restore. `DB_SSL` default `false` untuk pengembangan lokal.

## Konfigurasi Google

Di Google Cloud Console / Google Auth Platform, siapkan branding, audience (test users jika masih testing), lalu buat OAuth client bertipe **Web application**. Isi Authorized JavaScript origins sesuai URL frontend, misalnya `http://localhost:5173`. Masukkan client ID tersebut ke `GOOGLE_CLIENT_ID` backend dan konfigurasi Google Identity Services frontend.

Alur ini memakai JavaScript callback Google Identity Services: callback menerima `credential` (Google ID token), lalu frontend mengirim JSON `IdToken` ke backend. Tidak membutuhkan client secret atau redirect callback backend. Endpoint ini bukan penerima form POST langsung dari Google.

Backend memverifikasi tanda tangan, audience, issuer, expiry, dan email terverifikasi sebelum menyimpan user. Identitas akun memakai `sub` Google; email tidak dipakai untuk menggabungkan akun. Lihat [panduan resmi Google](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).

Verifikasi waktu ID token Google memiliki toleransi selisih jam maksimal 60 detik. Jika log menunjukkan `token_not_yet_valid_check_system_clock`, sinkronkan jam komputer/server, lalu coba login lagi dengan token baru. Di Windows gunakan Settings → Time & language → Date & time → Sync now.

## API autentikasi

### POST /auth/google

Request mengikuti PascalCase template:

```json
{"IdToken": "<credential-dari-callback-Google>"}
```

Respons `200`:

```json
{
  "AccessToken": "<jwt-aplikasi>",
  "TokenType": "bearer",
  "ExpiresIn": 3600,
  "User": {
    "Id": "<uuid>",
    "Email": "nama@gmail.com",
    "Name": "Nama Pengguna",
    "PictureUrl": "https://..."
  }
}
```

Login pertama membuat user. Login berikutnya memperbarui profil dan waktu login pada user yang sama. Semua akun Google dengan token valid dapat mendaftar; tidak ada pembatasan ke satu email pada tahap ini.

### GET /auth/me

Kirim header `Authorization: Bearer <AccessToken>` untuk mendapatkan profil user. Pakai dependency `get_current_user` pada endpoint keuangan berikutnya dan filter data berdasarkan `user.id`.

Status error: `401` token tidak valid/kedaluwarsa atau tidak ada, `403` akun nonaktif, `422` body salah, `503` konfigurasi autentikasi belum lengkap atau layanan verifikasi Google tidak tersedia. Error menggunakan format FastAPI `detail`.

Access token berlaku 60 menit, bisa diatur lewat `ACCESS_TOKEN_EXPIRE_MINUTES`. Refresh token dan pencabutan sesi belum dibuat. Saat kedaluwarsa, frontend perlu memperoleh ID token Google baru. Logout frontend membuang access token lokal; token yang telah diterbitkan tetap berlaku sampai kedaluwarsa. Menonaktifkan `users.is_active` langsung menolak akses berikutnya.

Frontend sebaiknya menyimpan token dalam memori dan mengirimnya lewat header Authorization; gunakan HTTPS untuk deployment. Backend tidak menetapkan cookie login. CORS mengizinkan origin yang dikonfigurasi di `ORIGINS`.

## Tagihan: setup akun

Tahap Add Account menyediakan daftar platform dari DB serta create/list/detail akun pengguna pada `/billing/platforms` dan `/billing/accounts`. Field kartu hanya wajib untuk `CREDIT_CARD`; fixed bill date mengontrol BillingDate dan DueDate (1–31). Nomor kartu disimpan sebagai ciphertext AES-256-GCM dan API hanya mengembalikan `AccountNumberMasked`.

Baseline `database/000_init.sql` sekarang mencakup seluruh fitur sampai migration 012. Database baru cukup menjalankan 000; jangan menjalankan 001–012 lagi. Untuk database lama, jalankan hanya migration yang belum diterapkan. Script 000 secara default (`finance_tracker.reset = on`) mengosongkan users, accounts, transactions, installments, debts, debt_payments, bank_accounts, savings, dan saving_movements melalui TRUNCATE, sambil mempertahankan wallet_providers. Gunakan `off` untuk init tanpa menghapus data; lihat [database/README.md](database/README.md) untuk dampak dan langkahnya.

Sesuaikan parameter koneksi di atas dengan `.env`. Backend membutuhkan `ENCRYPTION_KEY` (64 karakter hex / 32 byte) yang berbeda dari JWT SECRET_KEY. Bila belum tersedia, generate sekali dengan `python -c "import secrets; print(secrets.token_hex(32))"`. Pertahankan key ini untuk membaca nomor yang sudah disimpan, lalu restart backend setelah setup.

Catatan integrasi FE, contoh request/response, dan field kondisional: [docs/billing-frontend-notes.md](docs/billing-frontend-notes.md). Transaksi Sekali Bayar, Cicilan, Langganan, pembayaran, dan Transaction Date sudah tersedia; lihat [docs/billing-transactions.md](docs/billing-transactions.md).

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tes menggunakan SQLite sementara untuk persistence dan sertifikat RSA lokal untuk menjalankan verifikasi Google tanpa jaringan. Database aplikasi tetap PostgreSQL. Tes ini tidak menggantikan pengujian login Google nyata dengan client ID dan database deployment.

## Docker

```powershell
docker build -t finance-tracker-backend .
```

Compose yang tersedia memerlukan `IMAGE` dalam `.env` dan PostgreSQL eksternal. Untuk database di Windows host dari container, gunakan `DB_HOST=host.docker.internal`. `.dockerignore` mengecualikan `.env`, virtual environment, dan arsip dari image. Jalankan baseline SQL sebelum menjalankan API.

## Hutang & Piutang

Menu `/debts` di frontend tersambung ke API `/debts` melalui proxy sesi HttpOnly. Mendukung tanpa bunga atau persentase bunga bulanan dari sisa pokok, pembayaran sebagian/lunas, riwayat pembayaran, serta rincian bunga. Migration 007 menambah dua tabel tanpa mereset data lama. Aturan perhitungan, batas edit/hapus, dan endpoint: [docs/debts-receivables.md](docs/debts-receivables.md).

## My Bank Account

Menu /bank-accounts tersambung ke API backend untuk tambah, edit, dan hapus rekening debit, nomor tersensor, dan pencatatan biaya bulanan. Provider bersama memakai wallet_providers.BankF (kolom SQL bank_f), dengan bank dahulu di dropdown Tagihan. Lihat [panduan My Bank Account](docs/bank-accounts.md).



## Savings

Savings menyediakan tabungan uang, logam mulia (emas/perak) berdasarkan gram/keping, deposito, dan riwayat tambah/kurangi. Ringkasan nominal/gram terpisah; harga emas manual dan bunga deposito hanya informasi. Lihat [API dan aturan Savings](docs/savings.md).
