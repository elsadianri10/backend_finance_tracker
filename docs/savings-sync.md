# Penghubung Savings

Tombol Tambah / Kurangi dari menu Savings menyediakan `Catat juga di Transaksi`, aktif default untuk Tabungan Uang yang memiliki rekening. Tambah memakai rekening sumber lain dan menghasilkan transfer kategori Alokasi Tabungan; Kurangi menghasilkan Tarik Tunai dari rekening Savings ke tunai. Payload movement memakai `RecordTransaction=true` dan `SourceBankId` hanya untuk tambah. Movement dan ledger disimpan atomik, tanpa movement kedua. Jika hanya menyesuaikan saldo, matikan opsi tersebut. Logam Mulia dan Deposito tetap memakai riwayat sendiri.

Saldo awal dari Tambah Simpanan tidak membuat Transaksi. Riwayat lama tidak dibuat ulang; RequestId yang sama tidak membuat ledger/movement ganda dan tidak dapat dipakai untuk mengubah rekening sumber. Penghubung ini memakai kolom migration 018 yang sudah ada, tanpa migration baru.

Migration 018 menambahkan `routine_plans.saving_id` dan `ledger_transactions.saving_movement_id` dengan foreign key relasional. Tidak ada reset, backfill, atau penghitungan ulang pembayaran lama.

Di Transaksi, Pemasukan dengan kategori Tarik Tunai memakai rekening sumber, tujuan tunai, dan pilihan Savings. `SavingId` membuat movement REMOVE. Transfer Antar Rekening dengan kategori Alokasi Tabungan dan `SavingId` membuat movement ADD. Pilihan Savings hanya memuat Tabungan Uang (CASH); rekening harus sama dengan Savings yang dipilih. Tanpa pilihan Savings, transaksi tetap catatan biasa.

Di Pengeluaran Rutin, rencana TRANSFER dapat menyimpan `SavingId` bersama rekening tujuan yang sesuai. Pembayaran lewat menu rutin maupun lewat penghubung transaksi menghasilkan satu ledger dan satu movement ADD secara atomik. Hubungan baru hanya berlaku untuk pembayaran berikutnya. RequestId menjaga retry tetap menghasilkan satu movement.

Saldo yang tidak cukup, rekening berbeda, kepemilikan tidak sesuai, dan tanggal tidak berurutan ditolak tanpa perubahan parsial. Aturan tanggal Savings tetap berlaku: sejak tanggal mulai, tidak sebelum movement terakhir, dan tidak melewati hari ini.

Ledger tertaut tidak bisa diedit/dihapus manual. Pembatalan pembayaran rutin terakhir membuat movement kebalikan bertanggal hari pembatalan dan tetap menyimpan riwayat asal. Jika saldo sudah dipakai sehingga movement kebalikan tidak bisa dilakukan, pembatalan ditolak atomik. Savings yang terhubung ke ledger/rencana tidak dapat dihapus.

Jalankan `.venv/Scripts/python.exe tests/check_savings_sync_migration.py` untuk schema sintetis. `--apply` menerapkan migration setelah membandingkan seluruh record/kolom lama. Migration 018 telah diterapkan lokal 9 Oktober 2026; semua record sebelumnya tetap utuh.

Validasi: `tests/test_savings_sync.py` memeriksa tarik tunai, setoran langsung, pembayaran rutin dua arah, idempotensi, otorisasi, rollback, dan pembatalan. Proxy diuji melalui `npm run test:routines` dengan SQLite sintetis.
