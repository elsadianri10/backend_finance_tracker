# Hutang & Piutang

Semua endpoint memerlukan JWT aplikasi dan membatasi data menurut pengguna login. Frontend `/debts` membaca token hanya di route proxy server dari cookie HttpOnly; token tidak dikirim ke komponen browser. Semua fetch/respons proxy no-store. POST/PATCH/DELETE memakai pemeriksaan same-origin yang sama dengan login.

## Data dan fitur awal

- Jenis DEBT (Hutang: uang yang pengguna pinjam) atau RECEIVABLE (Piutang: uang yang pengguna pinjamkan).
- Nama orang, nominal pokok rupiah, tanggal transaksi, jatuh tempo opsional, notes.
- InterestType NONE dengan InterestRate 0, atau MONTHLY dengan InterestRate > 0 sampai 100%, maksimal 2 desimal.
- Pokok bilangan bulat > 0 sampai Rp 1 triliun; uang disimpan NUMERIC, bunga dihitung menggunakan Decimal.
- Tanggal transaksi sejak 2000-01-01 sampai hari ini (UTC+7). Jatuh tempo tidak boleh sebelum transaksi.
- Tab Hutang/Piutang dan filter Aktif/Lunas/Semua. Catatan diurutkan nama orang. Total tabel mengikuti filter. Ringkasan menunjukkan saldo seluruh hutang/piutang pada hari ini.
- Status lewat tempo hanya jika masih bersisa dan jatuh tempo sudah lewat. Catatan lunas tampil selama 3 bulan kalender sejak PaymentDate pembayaran terakhir yang melunasi seluruh pokok dan bunga. Pada tanggal tersebut + 3 bulan catatan disembunyikan dari daftar Lunas/Semua; akhir bulan dipangkas ke hari terakhir bulan tujuan (31 Maret → 30 Juni). Tanggal pembayaran historis tetap menjadi patokan, bukan tanggal input. Catatan aktif tidak dibatasi usia. Tidak ada penghapusan otomatis: seluruh catatan dan pembayaran tetap di database, dan detail milik user tetap bisa dibaca melalui GET /debts/{id}.
- Backend memfilter GET /debts dan menyertakan IsHistoryVisible pada respons daftar/detail/mutasi agar frontend juga menyembunyikan pelunasan historis yang sudah melewati batas. Perhitungan memakai tanggal lokal UTC+7 dan data pembayaran yang sudah tersimpan, tanpa migration atau scheduler.

## Bunga bulanan

Bunga pertama terbit satu bulan setelah tanggal transaksi; tanggal transaksi menjadi patokan bulanan. Tanggal 29–31 dipangkas ke hari terakhir pada bulan pendek, lalu kembali ke tanggal asal pada bulan berikutnya.

Bunga setiap periode = sisa pokok pada tanggal terbit x persentase bulanan / 100. Dibulatkan ke rupiah terdekat dengan ROUND_HALF_UP. Tidak ada prorata harian atau bunga berbunga. Bunga yang belum dibayar tidak menjadi pokok. Pembayaran pada tanggal terbit bunga dilakukan setelah bunga periode itu dihitung.

Pembayaran melunasi bunga yang terbit lebih dulu, lalu mengurangi pokok. Setelah saldo 0, tidak ada bunga berikutnya. Total = pokok awal + seluruh bunga yang sudah terbit; sisa = total - pembayaran. Bunga masa depan belum termasuk total. API menyertakan RemainingPrincipal, RemainingInterest, InterestCharges (tanggal, dasar sisa pokok, nominal), serta InterestPortion/PrincipalPortion pada setiap pembayaran.

Contoh: pokok Rp 1.000.000 tanggal 31 Januari 2026, bunga 2%. Pada 28 Februari terbit Rp 20.000. Pembayaran Rp 220.000 pada hari itu melunasi bunga Rp 20.000 dan pokok Rp 200.000. Pada 31 Maret bunga dihitung dari Rp 800.000, menjadi Rp 16.000. Sisa = Rp 816.000.

Perhitungan merekonstruksi kejadian dari tanggal transaksi dan pembayaran yang tersimpan sampai hari ini saat GET/mutasi; tidak memerlukan scheduler dan GET tidak menambah baris. Tanggal pembayaran boleh historis, tetapi tidak boleh sebelum tanggal transaksi/pembayaran sebelumnya atau sesudah hari ini. Nominal tidak boleh melebihi sisa pada tanggal pembayaran yang dipilih. Pelunasan historis menghentikan bunga sesudah tanggal tersebut.

## API

| Method | Path | Kegunaan |
| --- | --- | --- |
| GET | `/debts` | Daftar kedua jenis dan rincian saldo milik user |
| POST | `/debts` | Buat catatan, 201 |
| GET | `/debts/{id}` | Detail, rincian bunga, riwayat pembayaran |
| PATCH | `/debts/{id}` | Edit catatan |
| DELETE | `/debts/{id}` | Hapus hanya jika belum ada pembayaran, 204 |
| POST | `/debts/{id}/payments` | Tambahkan pembayaran, 201 |

Request create/update:

```json
{"Kind":"DEBT","PersonName":"Budi","Principal":1000000,"TransactionDate":"2026-01-31","DueDate":null,"InterestType":"MONTHLY","InterestRate":"2.00","Notes":""}
```

Request pembayaran:

```json
{"RequestId":"<uuid-baru-per-form>","Amount":220000,"PaymentDate":"2026-02-28","Notes":""}
```

RequestId menghindari pembayaran ganda ketika request yang sama diulang setelah gangguan koneksi. ID yang sama dengan isi berbeda ditolak 409. Mutasi mengunci baris parent dengan FOR UPDATE, sehingga pembayaran bersamaan tidak dapat melebihi saldo dan delete tidak dapat menghilangkan pembayaran yang baru masuk.

Sebelum pembayaran pertama semua field dapat diedit. Setelah ada pembayaran hanya nama, jatuh tempo, notes yang dapat diedit; pokok, jenis, tanggal transaksi, dan bunga terkunci. Riwayat pembayaran belum dapat diedit/dihapus pada versi awal. Hapus catatan memakai konfirmasi popup dan ditolak backend jika memiliki pembayaran. Pencatatan tidak memindahkan uang ke bank/orang lain.

401 sesi invalid; 403 user nonaktif; 404 catatan tidak ditemukan/bukan milik user; 409 konflik/edit syarat keuangan setelah pembayaran/hapus dengan riwayat; 422 field/nominal/tanggal invalid. Error form menggunakan detail[].loc. Kesalahan jaringan/backend ditampilkan sebagai layanan tidak tersedia.

## Database dan pengujian

Database lama: jalankan `database/007_debts_receivables.sql` sekali setelah migration yang sebelumnya diperlukan. Database baru: `000_init.sql` mencakup seluruh schema sampai 007. Script 000 default reset sekarang turut TRUNCATE debts dan debt_payments, serta tetap mempertahankan billing_platforms. Jangan gunakan 000 reset untuk upgrade.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_debts.py
.\.venv\Scripts\python.exe tests/check_debts_postgres.py
.\.venv\Scripts\python.exe tests/check_database_baseline.py
```

Frontend: `npm run build`, `npm run test:debts`. Preview sintetis terisolasi: `npm run test:debts -- --preview`; server mock saja, tidak memakai data aplikasi. Pengujian PostgreSQL/baseline menggunakan schema acak yang dibersihkan sesudahnya.

## Asal Dana, tanggal pengembalian, dan cicilan (migration 009)

Nama pada Piutang adalah nama peminjam yang berutang kepada pengguna; Nama pada Hutang adalah pemberi pinjaman. Piutang dapat mencatat SourceBankAccountId dari rekening milik pengguna di My Bank Account. Bank asal bukan transaksi pemindahan uang otomatis. Snapshot nama provider dan nomor rekening tersensor tetap tersimpan jika catatan bank kemudian dihapus; FK sumber menjadi NULL. Frontend bisa mempertahankan sumber lama saat edit atau memilih sumber lain. Tanpa data sumber, transaksi lama tetap valid.

DueDate tetap menjadi key API, kini berlabel Tanggal Pengembalian. Pada transaksi tanpa cicilan ini adalah janji pengembalian. Pada cicilan ini adalah tanggal cicilan pertama; berikutnya setiap bulan dengan hari asli dipertahankan dan diklem ke akhir bulan pendek (31 Januari → 28 Februari → 31 Maret). InstallmentCount menerima 0 untuk tanpa cicilan, atau 1–60. Tanggal pertama wajib untuk cicilan.

InstallmentAmounts adalah array nominal pokok positif. Jika tidak diberikan, backend membagi pokok secara bulat dan menempatkan sisa pembulatan pada cicilan terakhir. Jumlah seluruh nominal wajib sama dengan Principal. Rincian respons Installments berisi Sequence, DueDate, PrincipalAmount, PaidPrincipal, RemainingPrincipal dan IsPaid.

PATCH /debts/{id}/installments menerima {Amounts:[...]} untuk mengganti nominal cicilan. Jumlah elemen dan total harus sesuai tenor/pokok. Nominal cicilan yang sudah menerima pembayaran pokok, termasuk sebagian, tidak dapat diganti. Jumlah cicilan dan tanggal awal terkunci setelah ada pembayaran; edit nama, catatan, dan sumber tetap tersedia. Semua perubahan memakai lock baris debt yang sama dengan pembayaran, sehingga perubahan nominal/pembayaran tidak bertabrakan.

Nominal cicilan mengatur bagian pokok. Bunga tetap dihitung sesuai aturan sebelumnya, berdasarkan sisa pokok nyata pada setiap anniversary bulanan sejak TransactionDate, tanpa bunga berbunga atau pro rata. Pembayaran lebih dulu menutup bunga terbit lalu pokok, dan bagian pokok dialokasikan ke cicilan paling awal yang belum selesai. Pembayaran sebagian/lebih awal tetap diperbolehkan. Rencana cicilan tidak memprediksi bunga masa depan dan tidak mengubah nominal pokok transaksi. Status overdue mengikuti cicilan pokok yang jatuh tempo dan belum selesai; sisa bunga setelah tanggal terakhir juga overdue.

Migration 009 additive telah diterapkan lokal 7 Oktober 2026 tanpa reset. Rekaman lama memiliki installment_count=0 dan sumber NULL. Baseline 000 sudah mencakup 009; default reset tetap hanya data aplikasi, bukan provider. tests/test_debt_installments.py mencakup rentang tenor, pembulatan, akhir bulan, ownership sumber, snapshot setelah hapus bank, override, lock nominal parsial, dan bunga terpisah. Tes proxy FE juga mencakup PATCH installments, same-origin dan proyeksi nested response.

## Penyimpanan relasional (migration 019)

Rincian nominal cicilan disimpan di `debt_installments`: `debt_id` mengacu ke `debts`, `sequence` menjaga urutan 1–60, dan `amount` memakai NUMERIC(18,0). Primary key gabungan mencegah urutan ganda; nominal harus positif dan maksimal Rp 1 triliun. Kolom JSON `debts.installment_amounts` dihapus setelah backfill diverifikasi. `InstallmentAmounts` tetap berupa array pada API, tetapi bukan kolom JSON di database.

Migration 019 mempertahankan seluruh nominal/urutan cicilan, ketentuan hutang/piutang dan riwayat pembayaran. Data lama yang tidak valid membatalkan seluruh transaksi migration. Script verifikasi membuat backup lokal yang diabaikan Git serta membandingkan seluruh record sebelum commit. Baseline 000 sampai 019 hanya untuk database kosong atau pengujian schema sintetis; jangan menjalankannya untuk upgrade database aplikasi.
