# Script database PostgreSQL

- `000_init.sql`: baseline lengkap sampai versi 019 untuk database kosong, sekaligus mengosongkan data aplikasi secara default dengan TRUNCATE; isi wallet_providers tetap dipertahankan. Mencakup seluruh tabel keuangan, Pengeluaran Rutin, ledger Transaksi, semua constraint/index, dan 7 platform default (termasuk Blibli Pay Later).
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
- Perubahan berikutnya memakai `020_...`, `021_...`, dan seterusnya. Penambahan kolom juga memakai nomor berikutnya. Fitur baru memakai tabel relasional dan kolom bertipe, tanpa JSON/JSONB.
- Database baru: jalankan 000 saja; 001–019 sudah tergabung dan tidak perlu dijalankan lagi. Database lama: gunakan hanya migration yang belum diterapkan, berurutan dan sekali per database. Catat versi yang sudah diterapkan. Tidak ada auto-migration saat aplikasi mulai.
- 000 adalah snapshot baseline terkini; perubahan 000 tidak dipakai untuk upgrade database yang sudah berjalan. Jangan ubah migration historis 001 dan seterusnya. Tambahkan file baru dengan `ALTER TABLE` atau `CREATE TABLE` dan transaksi `BEGIN` / `COMMIT`.
- Buat database terlebih dahulu; script tidak membuat database atau user PostgreSQL.

```powershell
createdb -h localhost -p 5432 -U postgres finance_tracker
psql -h localhost -p 5432 -U postgres -d finance_tracker -v ON_ERROR_STOP=1 -f database/000_init.sql
```

## Mode init dan reset

Di awal `000_init.sql` terdapat:

```sql
SELECT set_config('finance_tracker.reset', 'on', true);
```

- `on` (default): membuat tabel yang belum ada, lalu menjalankan `TRUNCATE` seluruh tabel aplikasi, termasuk `ledger_transactions`, `routine_payments`, `routine_plans`, dan `transaction_imports`. Semua grup Split Bill, rencana rutin dan pembayaran, ledger transaksi, simpanan, hutang/piutang, tagihan, akun, dan pengguna dihapus. Struktur tabel serta seluruh isi `wallet_providers` (termasuk platform custom/status aktif) tetap dipertahankan. Seed default yang belum ada ditambahkan tanpa menimpa platform lama. Akun Google perlu login kembali; kunci enkripsi tidak berubah.
- `off`: hanya membuat tabel yang belum ada dan menambahkan seed yang belum ada; data aplikasi tidak dikosongkan.

Jalankan seluruh file memakai `psql ... -v ON_ERROR_STOP=1 -f database/000_init.sql`. Pastikan database/schema tujuan benar. Script bekerja di schema aktif (`search_path`), tidak memakai DROP maupun TRUNCATE CASCADE. Foreign key dari tabel lain dapat membuat reset gagal; seluruh operasi dibatalkan oleh transaksi. Struktur lama tetap perlu migration yang belum diterapkan sampai 019 sebelum menjalankan script ini. Matikan backend saat reset agar tidak ada request bersamaan.

Reset belum dijalankan pada database aplikasi. Pengujian init/reset memakai schema acak dengan data sintetis:

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

