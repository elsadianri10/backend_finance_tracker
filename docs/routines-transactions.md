# Pengeluaran Rutin dan Transaksi

Migration 016 menambahkan empat tabel relasional dengan nominal rupiah bulat BIGINT, tanggal DATE, FK kepemilikan, CHECK, dan indeks unik. Migration 017 menambahkan hubungan Hutang pada rencana serta DebtPaymentId dan pengenal request pada ledger. Tidak memakai JSON/JSONB. Migration tidak mengubah record keuangan lama. `000_init.sql` adalah baseline/reset, bukan upgrade database aplikasi.

## Rencana

`GET/POST /routine?month=YYYY-MM`, `PATCH /routine/{id}?month=...`, `DELETE /routine/{id}`, dan `GET /routine/options`. Seluruh endpoint memakai JWT serta kepemilikan pengguna; respons no-store. Payload PascalCase: Kind, Recipient, Name, Amount, Status, FirstDueDate, IntervalMonths, TotalCycles, InitialPaid, DestinationBankId, BillingTransactionId, Notes. PATCH juga mengirim Version; konflik versi mengembalikan 409.

- Kind SUBSCRIPTION untuk langganan, CONTRIBUTION untuk bantuan/setoran, TRANSFER untuk alokasi rekening sendiri. Setoran berbeda pada penerima yang sama tetap menjadi rencana terpisah.
- Status ACTIVE, NOTE, atau STOPPED. FINISHED dihitung setelah seluruh cicilan tercatat. NOTE dapat bernominal nol; hanya ACTIVE masuk kebutuhan bulan tersebut.
- TotalCycles 0 berarti berlanjut; 1–60 berarti terbatas. InitialPaid mencatat progres sebelum menggunakan aplikasi, tanpa membuat transaksi palsu. FirstDueDate adalah tanggal pembayaran pertama yang belum dicatat setelah InitialPaid.
- Jadwal interval 1–12 bulan dihitung dari tanggal awal; 31 Oktober menjadi 30 November dan 31 Desember. Progres mengikuti pencatatan pembayaran, bukan pergantian bulan.
- Ringkasan bulan memakai periode jatuh tempo. Ledger memakai tanggal realisasi pembayaran. Alokasi tabungan dipisahkan dari kebutuhan pengeluaran.
- Setelah pembayaran aktif tercatat, jenis/jadwal/progres awal/relasi Tagihan dikunci. Nominal dan catatan dapat diubah untuk pembayaran berikutnya. Rencana yang pernah memiliki riwayat tidak dapat dihapus; dapat dihentikan.

## Pembayaran

`POST /routine/{id}/payments?month=...` menerima RequestId UUID, Sequence berikutnya, Amount aktual, PaymentDate, SourceBankId opsional, BillingInstallmentId opsional, dan Notes. Plan dikunci selama transaksi; pembayaran, ledger, dan versi plan disimpan bersama. Pengulangan RequestId dengan payload sama mengembalikan pembayaran yang sama; payload berbeda atau RequestId yang sudah dibatalkan menghasilkan 409.

`DELETE /routine/{id}/payments/{paymentId}?month=...` membatalkan pencatatan pembayaran aktif terakhir dan ledger terkait secara atomik. Riwayat void dipertahankan; siklus yang sama dapat dicatat lagi dengan RequestId baru. Pembatalan pencatatan tidak melakukan transfer uang.

TRANSFER membutuhkan dua rekening berbeda milik pengguna. Pilihan rekening dan label tersamarkan berasal dari My Bank Account. Tidak menghitung transfer sebagai pemasukan atau pengeluaran, tidak mengubah saldo riil rekening, dan tidak membuat SavingMovement.

Rencana dapat menunjuk BillingTransaction atau Debt milik pengguna, satu sumber per rencana. Hutang tertaut hanya untuk CONTRIBUTION dan hanya Debt berjenis DEBT. Satu sumber hanya boleh memiliki satu rencana ACTIVE. Pembayaran tertaut memperbarui Tagihan/Hutang, progres rencana, dan satu ledger secara atomik. Untuk Tagihan, pilih installment berikutnya yang belum dibayar; nominal harus persis sama. Rincian lama yang sudah dibayar dan belum terhubung ke rutin dapat diasosiasikan tanpa menggandakan ledger.

Konfirmasi Sudah Dibayar di Tagihan membuat ledger dengan tanggal paid_at saat konfirmasi, dikonversi ke UTC+7, bukan tanggal jatuh tempo. Hutang/Piutang memakai PaymentDate yang dipilih: pembayaran hutang menjadi expense/debt, penerimaan piutang menjadi income/receivable. Pembayaran dari menu asal juga menambah progres rencana ACTIVE tertaut. Riwayat tertaut tidak dapat diedit/dihapus sebagai transaksi manual; undo Pengeluaran Rutin hanya tersedia bagi pembayaran tanpa hubungan Tagihan/Hutang.

## Ledger Transaksi

`GET/POST /transactions`, `PATCH/DELETE /transactions/{id}`. Payload: Kind income/expense/transfer, Description, Category, Amount, TransactionDate, SourceBankId, DestinationBankId, Notes. POST dapat mengirim satu dari DebtId, BillingInstallmentId, atau RoutinePlanId + RoutineSequence, dengan RequestId UUID. Pilihan penghubung menentukan catatan mana yang harus dibayar; memilih kategori saja tidak mengubah hutang/tagihan. RequestId dan hash payload mencegah pengulangan membuat pembayaran baru. Mutasi pembayaran diserialisasi per pengguna lalu mengunci parent; kepemilikan semua sumber dan rekening diperiksa. Pembayaran tertaut dan ledger commit bersama, termasuk rollback saat nominal/jadwal tidak valid. Penghapusan ledger manual memakai void; GET hanya mengembalikan record aktif.

Untuk transaksi tertaut ke Tagihan, TransactionDate tidak mengganti tanggal konfirmasi; server memakai paid_at. Histori sebelum fitur sinkronisasi tidak dibuat ulang otomatis untuk menghindari penghitungan ganda dengan catatan lama.

`POST /transactions/import` menerima Transactions dari struktur browser lama (id, description, type, category, amount, date). Import mengunci pengguna, membuat ID deterministik, dan menyimpan marker satu kali. Pengulangan tidak menggandakan data atau menghidupkan kembali transaksi yang dihapus. FE mempertahankan localStorage lama sebagai cadangan dan demo tetap terpisah. Import lama mencakup income/expense saja.

## Verifikasi

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_routines.py
.\.venv\Scripts\python.exe tests/apply_routine_migration.py
.\.venv\Scripts\python.exe tests/check_database_baseline.py
.\.venv\Scripts\python.exe tests/check_payment_sync_migration.py
```

Upgrade dan reset pengujian berjalan pada schema PostgreSQL acak dengan data sintetis. `tests/apply_routine_migration.py --apply` hanya menerapkan upgrade additive 016 ke database konfigurasi dan membandingkan semua record sebelumnya, tanpa seed/reset database aplikasi.
