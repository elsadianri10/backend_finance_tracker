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


## Pembayaran utang dan pengembalian piutang (28 Oktober 2026)

`POST /debts/{id}/payments` menerima `SavingId` opsional bersama `BankAccountId` yang cocok dengan rekening Tabungan Uang terpilih (keduanya boleh null untuk tabungan tunai). Utang membuat mutasi REMOVE; pengembalian piutang membuat ADD. Relasi tetap `ledger_transactions.debt_payment_id` dan `saving_movement_id`: hanya satu ledger per pembayaran, tanpa transaksi Tarik Tunai atau Alokasi Tabungan tambahan. Tidak ada perubahan schema/migrasi.

Alur yang sama tersedia lewat `POST /transactions` dengan `DebtId` + `SavingId`. Savings juga dapat dipakai untuk pengeluaran Bill/Routine seperti penjelasan berikut. Pengeluaran utang tetap kategori debt dan pengembalian piutang kategori receivable; pengembalian piutang mengikuti perhitungan arus kas yang sudah ada, bukan pendapatan baru.

Pemilik dikunci sebelum utang dan Savings; pembayaran, ledger, progres rutin terkait dan mutasi Savings disimpan dalam satu commit. Saldo cukup, batas saldo, pemilik, CASH, rekening dan urutan tanggal Savings tetap divalidasi. Kegagalan membatalkan seluruh pencatatan. RequestId berulang dengan nominal/tanggal/catatan/target yang sama mengembalikan hasil sebelumnya, tanpa menggandakan mutasi; perubahan rekening/target ditolak. Mutasi menggunakan ID deterministik dari pembayaran, sehingga ID permintaan yang kebetulan sama di dua utang tidak berbagi satu mutasi.

Form Hutang & Piutang menyediakan checkbox opsional default off; daftar Savings dimuat saat diaktifkan. Tabungan dan rekeningnya dikirim bersama. Form Transaksi menampilkan dropdown Savings saat memilih utang/piutang dan mengikuti rekening tabungan tersebut. Respons pembayaran `SavingUpdated` mengarahkan refresh hanya ke Savings yang terpengaruh. Kegagalan memuat pilihan dapat dicoba lagi atau opsi dimatikan untuk pembayaran biasa.

Pembayaran/penarikan lama tidak ditautkan ulang otomatis. Jangan mencatat ulang pembayaran yang sudah ada hanya untuk memilih Savings; tindakan tersebut akan menjadi pembayaran baru. Pengujian: `tests/test_debt_savings.py`, `test_payment_sync.py`, `test_savings_sync.py`, `test_debts.py` memakai SQLite in-memory sintetis. Tidak ada perubahan database aplikasi saat verifikasi.


## Sumber Savings untuk pengeluaran rutin, Tagihan, dan stok

SavingId opsional pada `POST /routine/{id}/payments`, `POST /billing/transactions/{id}/installments/{id}/pay`, dan `POST /stock-needs/{id}/products/{id}/purchases` mengurangi Tabungan Uang terpilih. Rekening sumber wajib cocok dengan rekening tabungan; tabungan tunai tanpa rekening memakai source null. Pembelian stok wajib RecordExpense=true dan Amount>0. Pembayaran rutin jenis TRANSFER tidak menerima sumber Savings ini; tujuan Savings alokasi tabungan yang sudah ada tetap terpisah.

Endpoint Tagihan tetap menerima request tanpa body atau `{}`. Tagihan yang sudah dibayar ditolak 409, sehingga pengiriman ulang tidak menimbulkan pengeluaran atau mutasi baru. Rutin memakai RequestId/sequence dan stok memakai RequestId/fingerprint. Target berbeda pada retry ditolak. Pembayaran lama tidak ditautkan ulang; lampiran rutin ke Tagihan lama tidak membuat withdrawal baru. Relasi existing ledger ke saving_movements cukup, tidak ada migration baru.

Semua pencatatan berada di transaksi DB yang sama dan dikunci berdasarkan pemilik. Saldo tidak cukup/jenis bukan CASH/target pemilik lain/rekening atau tanggal tidak cocok menggagalkan seluruh pembayaran serta progres stok. Pembatalan rutin biasa mengembalikan saldo melalui mutasi kebalikan; pembayaran rutin terkait utang/Tagihan tetap tidak dapat dibatalkan lewat Rutin.

Form menampilkan pilihan Bayar dari Savings default off. Daftar dimuat saat dibutuhkan; sumber rekening mengikuti tabungan dan tombol simpan menunggu pilihan valid. Stok menyembunyikan serta membersihkan pilihan ketika RecordExpense dimatikan. Transaksi juga menerima SavingId bersama BillingInstallmentId/RoutinePlanId untuk pengeluaran. Respons SavingUpdated dan SavingMovementId mengarahkan refresh Savings, ledger dan ringkasan; tidak menambah Pendapatan atau Tarik Tunai fiktif.

Verifikasi sintetis: tests/test_savings_expenses.py mencakup sukses/gagal, rollback, retry, undo, rutin terhubung utang/Tagihan, dan kedua titik masuk Transaksi. npm run test:routines memeriksa ketiga alur melalui proxy frontend dengan API SQLite in-memory. Data aplikasi tidak diubah.
