# Script database PostgreSQL

- `000_init.sql`: baseline PostgreSQL sampai 037. Membuat struktur dan seed yang belum tersedia serta mempertahankan data yang ada. Gunakan migrasi bernomor untuk database lama.
- `001_create_billing_accounts.sql`: platform bank/paylater, relasi tipe yang didukung, akun milik pengguna, dan seed BCA, BRI, GoPay Later, ShopeePay Later.
- `002_create_billing_transactions.sql`: transaksi per akun dan jadwal cicilan, nominal NUMERIC, serta waktu pembayaran. Telah dijalankan pada database lokal 7 Oktober 2026. Database lain perlu menjalankan script ini sekali.
- `003_merge_billing_platform_types.sql`: memindahkan tipe ke kolom nullable `billing_platforms.platform_type`, mempertahankan batasan tipe lama, mengganti foreign key akun, dan menghapus tabel relasi lama. Telah dijalankan pada database lokal 7 Oktober 2026. NULL mengizinkan kedua tipe akun.
- `004_account_only_platform_type.sql`: menghapus kolom tipe dari platform; tipe hanya tersimpan di akun dengan NOT NULL dan CHECK CREDIT_CARD/PAY_LATER. Telah dijalankan pada database lokal 7 Oktober 2026.
- `005_billing_subscriptions.sql`: jenis transaksi dan langganan bulanan, tanggal penghentian, snapshot tanggal CC, serta tanggal penagihan pada rincian. Telah dijalankan pada database lokal 7 Oktober 2026.
- `006_billing_transaction_date.sql`: menambahkan tanggal transaksi, tanpa mengubah jadwal lama. Telah dijalankan pada database lokal 7 Oktober 2026.
- `007_debts_receivables.sql`: menambahkan `debts` dan `debt_payments` untuk hutang/piutang, bunga bulanan dari sisa pokok, dan pembayaran bertahap. Telah dijalankan pada database lokal 7 Oktober 2026; data lama tetap dipertahankan.
- `010_savings.sql`: tabungan uang, emas fisik, deposito, dan riwayat tambah/kurangi. Upgrade additive tanpa reset. Lihat [Savings](../docs/savings.md).
- `014_split_bills.sql`: skema historis awal Split Bill. Database lama pada versi ini perlu upgrade 015.
- `015_split_bill_relational.sql`: memigrasikan Split Bill ke lima tabel relasional dan menghapus kolom document setelah backfill; jalankan melalui `python tests/check_split_bill_migration.py --apply` untuk backup dan perbandingan lengkap sebelum commit. Telah diterapkan lokal 9 Oktober 2026 tanpa reset. Matikan API sebelum upgrade dan restart sesudahnya. Lihat [Split Bill](../docs/split-bills.md).
- `013_billing_account_fees.sql`: fee bulanan dan fee pembayaran akun Tagihan, default 0.
- `012_savings_price_date.sql`: tanggal harga per gram manual; harga lama tetap tanpa tanggal.
- `011_savings_precious_metals.sql`: pilihan Emas/Perak pada Logam Mulia, dengan data emas lama diberi metal_type GOLD.
- `016_routines_transactions.sql`: empat tabel relasional `routine_plans`, `routine_payments`, `ledger_transactions`, dan `transaction_imports`. Upgrade additive, tanpa reset dan tanpa JSON/JSONB. Jalankan melalui `.\.venv\Scripts\python.exe tests/apply_routine_migration.py --apply` untuk memeriksa seluruh data lama sebelum/sesudah commit. Telah diterapkan lokal 9 Oktober 2026; semua tabel dan record sebelumnya tidak berubah. Lihat [Pengeluaran Rutin dan Transaksi](../docs/routines-transactions.md).
- `017_payment_sync.sql`: penghubung pembayaran dua arah antara ledger Transaksi, Tagihan, Hutang/Piutang, dan rutin; nominal/status/progres tersimpan atomik. Diterapkan lokal 9 Oktober 2026 melalui `.\.venv\Scripts\python.exe tests/check_payment_sync_migration.py --apply`; seluruh record lama dipertahankan tanpa backfill/reset.
- `018_savings_sync.sql`: Savings terhubung ke tarik tunai, alokasi Transaksi, dan pembayaran rutin; ledger/movement atomik tanpa backfill. Telah diterapkan lokal 9 Oktober 2026 melalui `tests/check_savings_sync_migration.py --apply`; seluruh record lama dipertahankan. Lihat [Penghubung Savings](../docs/savings-sync.md).
- `019_debt_installments_relational.sql`: nominal cicilan Hutang/Piutang dipindahkan dari JSON `debts.installment_amounts` ke `debt_installments` (debt_id, sequence, amount). Jalankan `tests/check_debt_installment_migration.py` untuk uji schema sintetis atau tambahkan `--apply` untuk backup serta perbandingan seluruh data sebelum commit. Telah diterapkan ke database lokal 10 Oktober 2026; seluruh record dan urutan/nominal cicilan identik, tanpa reset. Hentikan API sebelum upgrade database lain dan restart/deploy backend setelah upgrade.
- `020_split_bill_discount.sql`: menambahkan kolom BIGINT `discount` dengan default 0 pada pengeluaran Split Bill. Data/perhitungan lama dipertahankan. Uji schema sintetis: `tests/check_split_discount_migration.py`; tambahkan `--apply` untuk backup dan pemeriksaan seluruh record sebelum commit. Telah diterapkan pada database proyek 12 Oktober 2026 tanpa reset. Database deployment terpisah perlu upgrade 020 sebelum backend terbaru dijalankan.
- `021_passkeys.sql`: menambah `users.auth_version` dan tiga tabel relasional passkey/challenge/kode pemulihan. Tidak mengubah data keuangan atau mengaktifkan passkey akun secara otomatis. Uji: `tests/check_passkey_migration.py`; `--apply` membuat backup dan membandingkan seluruh record sebelum commit. Diterapkan pada database proyek 12 Oktober 2026 tanpa reset. Konfigurasi domain/deployment: [Passkey](../docs/passkeys.md).
- `025_stock_product_replenishment.sql`: dua kolom override jeda/penundaan beli ulang per produk, default lama tetap aktif. Jalankan setelah 024. Uji data terisi/upgrade berulang/baseline hanya di schema sintetis: `tests/check_stock_migration.py`.
- `024_stock_needs.sql`: tiga tabel stok kebutuhan/produk/riwayat bertipe. Additive, tanpa perubahan data keuangan/Wishlist; jalankan setelah 023. Uji upgrade berulang, data terisi, pembelian bersamaan dan baseline/reset hanya dalam schema sintetis: `tests/check_stock_migration.py`.
- Perubahan berikutnya memakai `037_...` dan seterusnya. Penambahan kolom juga memakai nomor berikutnya. Fitur baru memakai tabel relasional dan kolom bertipe, tanpa JSON/JSONB.
- Database baru memakai 000 yang sudah mencakup 001–037. Database lama memakai migrasi yang belum diterapkan sesuai urutan. Catat versi yang sudah diterapkan. Migrasi dijalankan terpisah sebelum aplikasi mulai.
- 000 adalah snapshot baseline terkini; perubahan 000 tidak dipakai untuk upgrade database yang sudah berjalan. Jangan ubah migration historis 001 dan seterusnya. Tambahkan file baru dengan `ALTER TABLE` atau `CREATE TABLE` dan transaksi `BEGIN` / `COMMIT`.
- Buat database terlebih dahulu; script tidak membuat database atau user PostgreSQL.

```powershell
createdb -h localhost -p 5432 -U postgres finance_tracker
psql -h localhost -p 5432 -U postgres -d finance_tracker -v ON_ERROR_STOP=1 -f database/000_init.sql
```

## Inisialisasi, preflight, dan reset

Jalankan `000_init.sql` untuk schema baru. Untuk schema aplikasi yang sudah berjalan, terapkan migrasi bernomor yang belum ada. Perubahan pada baseline tidak menggantikan migrasi tersebut.

Sebelum deploy, jalankan `.venv/Scripts/python.exe scripts/release_preflight.py` dengan konfigurasi database tujuan. Skrip hanya membaca database dan memeriksa tabel dan kolom yang dibutuhkan model serta constraint lama yang dilepas oleh migrasi 033. Kode keluar 1 berarti struktur wajib belum cocok atau pemeriksaan database gagal. Status `PENDING` untuk konfigurasi opsional tetap dilaporkan terpisah.

Reset data merupakan pemeliharaan terpisah melalui `reset_application_data.sql`. Skrip ini mengosongkan tabel aplikasi pada schema yang dipilih dan mempertahankan `wallet_providers` serta tabel lain. Untuk reset yang disengaja, hentikan backend, pastikan backup dan target sudah benar, lalu set `finance_tracker.confirm_reset` ke nama database dan schema tujuan, misalnya `finance_tracker_test.public`, pada sesi SQL yang sama. Reset menolak konfirmasi yang tidak sama dengan target aktif dan menghabiskan konfirmasi setelah berhasil. Jangan set konfirmasi menggunakan hasil otomatis dari koneksi yang belum diperiksa.

Pengujian baseline, reset, dan preflight memakai schema acak dengan data sintetis:

```powershell
.\.venv\Scripts\python.exe tests/check_database_baseline.py
```

`users.id` memakai UUID dari aplikasi. `google_sub` unik dan merupakan identitas akun Google; email hanya data profil dan tidak dipakai untuk menggabungkan akun. Waktu disimpan sebagai `TIMESTAMPTZ`. `updated_at` diperbarui oleh SQLAlchemy; perubahan SQL manual perlu mengisi timestamp itu sendiri.

Untuk tabel keuangan berikutnya, simpan nominal memakai `NUMERIC`, bukan floating point, dan tautkan kepemilikan data ke `users.id`.


Setelah script 004, platform hanya menyimpan identitas dan status aktif. Menambahkan platform cukup satu baris (gunakan ID yang belum terpakai):

```sql
INSERT INTO wallet_providers (id, name, bank_f)
VALUES (8, 'Platform Baru', 0);
```

`platform_type` hanya ada di `billing_accounts`, wajib diisi `CREDIT_CARD` atau `PAY_LATER`. API platform tetap mengembalikan `SupportedTypes` berisi kedua tipe untuk menjaga kompatibilitas FE. Semua platform aktif (`is_active = TRUE`) muncul dalam dropdown; pilihan tipe disimpan per akun pengguna.

Migration 008 mengganti nama platform menjadi wallet_providers dan menambahkan bank_f (0/1) serta bank_accounts. Telah diterapkan lokal 7 Oktober 2026 tanpa reset. Lihat [My Bank Account](../docs/bank-accounts.md) untuk API, biaya bulanan, dan pengelolaan provider bank.


Migration 009 menambahkan sumber rekening pada Piutang dan rencana cicilan 1–60 kali, tanpa mengubah pembayaran atau ketentuan transaksi lama. Telah diterapkan lokal 7 Oktober 2026. Detail: [Hutang & Piutang](../docs/debts-receivables.md).


## Wishlist versi 022

Database yang sudah pada 021: jalankan hanya `022_wishlists.sql` untuk menambah lima tabel Wishlist relasional tanpa mengubah data lama. Detail fitur dan verifikasi ada di `docs/wishlists.md`. Tidak ada auto-migration saat startup.

- `026_account_access.sql`: tabel account_access/access_audit untuk status paket dan Pro gratis admin. Additive, tidak mengubah data keuangan. Akun tanpa record akses berstatus Gratis. Uji hanya schema sintetis: `tests/check_access_migration.py`. Konfigurasi: `docs/account-access.md`.

- `027_account_trial.sql`: trial Pro 30 hari (720 jam) sekali per akun. Akun lama dimulai saat migrasi; akun baru dimulai pada login Google terverifikasi pertama. Pemberian Pro gratis/langganan dan data keuangan dipertahankan. Uji schema sintetis: `tests/check_trial_migration.py`. Jalankan setelah 026 dan sebelum deploy backend trial.

Migration 028_subscriptions.sql menambah subscription_orders dan subscription_payments (tanpa JSON), tidak mengubah data keuangan. Jalankan setelah 027 sebelum deploy langganan. Checkout/autodebit default nonaktif sampai environment Midtrans dikonfigurasi.

- `029_plan_archives.sql`: kolom archived pada rekening/Savings, default false untuk seluruh data lama. Tidak mengubah saldo, mutasi, link keuangan atau hak akses. Arsip/pemulihan memakai pemeriksaan kepemilikan dan slot aktif.

- 030_account_deletions.sql: antrean permintaan/pemeriksaan penghapusan dan pembersihan Blob; tidak mengubah record keuangan lama.

- `031_user_admin_roles.sql`: users.admin_f 0/1 dan riwayat perubahan admin; akun elsadianri10@gmail.com menjadi admin awal. Hak Pro serta data keuangan dipertahankan.


## Upgrade Neon dari 022 ke 031

Untuk Neon yang belum menjalankan migrasi 023–031, jalankan seluruh `upgrades/neon_upgrade_023_031.sql` pada branch/database yang digunakan backend. File ini menggabungkan sembilan migrasi dalam satu transaksi tanpa reset atau penghapusan data keuangan. Migrasi 027 memulai trial 30 hari bagi akun lama yang belum memiliki trial; migrasi 031 menetapkan `admin_f=1` untuk elsadianri10@gmail.com. Eksekusi ulang tidak memperpanjang trial yang sudah dimulai.

File `upgrades/neon_repair_023_025.sql` hanya mencakup tiga migrasi tersebut dan tidak cukup untuk Neon yang belum menerima 026–031. Setelah menjalankan gabungan 023–031, tidak perlu menjalankan file asal 023–031 lagi. Jangan memakai `000_init.sql` untuk upgrade database berisi data. Status migrasi PostgreSQL lokal tidak membuktikan status database Neon.


- `032_split_bill_share_links.sql`: tabel hash link berbagi per grup Split Bill. Jalankan setelah 031 sebelum backend fitur berbagi dipasang. Grup lama tetap pribadi; tidak ada link yang otomatis dibuat. Hanya menambah tabel, tanpa mengubah data keuangan. Uji: `tests/check_split_bill_share_migration.py` memakai schema sintetis terpisah. Gabungan Neon 023–031 tidak mencakup 032; jalankan 032 setelah gabungan tersebut.


- `033_allow_same_account_transfers.sql`: melepas constraint `ck_ledger_distinct_banks` agar rekening sumber dan tujuan boleh sama pada transfer internal. Jalankan sebelum memakai backend yang mengizinkan transfer internal; tidak mengubah baris transaksi atau saldo lama. Uji: `tests/check_same_account_transfer_migration.py` dalam schema sintetis. File gabungan 023–031 tidak mencakup 032/033.

- `034_transaction_versions_wishlist_cleanup.sql` memberi transaksi lama versi awal 1 dan menambah tabel antrean `wishlist_blob_cleanup`. Nominal, tanggal, dan referensi foto lama tetap tersimpan. Jalankan setelah 033 dan sebelum deploy backend baru. Reset terpisah mempertahankan antrean Blob yang belum selesai.

## Upgrade Neon dari 025 ke 034

Jika Neon sudah sampai 025, jalankan seluruh [gabungan migrasi 026–034](upgrades/neon_upgrade_026_034.sql) dalam satu kali eksekusi di SQL Editor. File memakai satu transaksi dan mempertahankan data keuangan. Migrasi 027 memulai trial 30 hari bagi akun lama yang belum punya trial, dan migrasi 031 menetapkan admin awal. Setelah berhasil, jalankan `scripts/release_preflight.py` dengan konfigurasi Neon tujuan sebelum deploy.

[Migrasi 035](035_budgeting.sql) menambah tabel Budgeting, kategori, dan item. Untuk deployment yang sudah sampai 034, jalankan 035 lalu preflight sebelum rilis Budgeting. Migrasi ini mempertahankan transaksi keuangan yang sudah ada.

[Migrasi 036](036_shared_subscriptions.sql) menambah tabel Patungan Langganan dan tautan unik ke transaksi uang masuk yang sudah ada. Terapkan setelah 035 dan jalankan preflight sebelum deployment.

[Migrasi 037](037_close_shared_subscriptions.sql) menambah tanggal tutup Patungan Langganan. Grup lama tetap aktif. Terapkan setelah 036 dan jalankan preflight sebelum deployment.
