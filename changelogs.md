# CHANGELOGS
## BACKEND - FINANCE TRACKER

<be>
<br>

---


# Developer Changelogs:

## [v.1.0.0-Unrelease]

### 2026-10-08

- Fee Tagihan: 9 tes backend, upgrade sintetis 013, baseline init/reset, lint, build, dan tes proxy lolos. Form tambah default 0, edit fee dan total akun diverifikasi dengan data sintetis; screenshot preview/billing-account-fees.png.

- Tagihan: MonthlyFee dan PaymentFee per akun, rupiah bulat nonnegatif default 0, tersedia pada create/detail/list/update. Edit dari klien lama mempertahankan fee yang tidak dikirim. Migration 013 menambahkan kolom/constraint tanpa reset; baseline 000 sampai 013.

- Verifikasi tanggal harga hanya berubah bersama nominal: 7 tes Savings, lint, build, dan tes proxy lolos. Tanggal di bawah estimasi emas/perak diperiksa memakai data sintetis; preview di preview/savings-estimate-date.png.

- Savings: PriceDate hanya berubah saat harga per gram diisi/berubah; edit metadata dan perubahan jumlah mempertahankan tanggal. Harga historis tanpa tanggal tetap NULL sampai harga berubah.

- Savings: tanggal harga otomatis di server setiap simpan form yang memiliki harga per gram (UTC+7); tambah/kurangi saldo tetap mempertahankan tanggal harga. Tidak membutuhkan migration tambahan.

- Tanggal harga Savings: 7 tes backend, upgrade sintetis 011→012, baseline init/reset, lint, build, dan tes proxy lolos. Kalender dan penyimpanan tanggal diverifikasi dengan data sintetis; preview di FE preview/savings-price-date.png.

- Savings: PriceDate mencatat tanggal harga emas/perak manual. Migration 012 menambahkan kolom nullable tanpa menebak tanggal harga lama; baseline 000 mencakup sampai 012. Perubahan saldo atau edit metadata mempertahankan tanggal harga.

- Savings: kategori Emas Fisik menjadi Logam Mulia dengan MetalType GOLD/SILVER. Identifier Kind GOLD tetap kompatibel; edit tanpa MetalType mempertahankan jenis logam sebelumnya.
- Migration 011 mengklasifikasikan emas lama sebagai GOLD tanpa mengubah kuantitas, harga, atau riwayat. Baseline 000 mencakup sampai 011.
- Jenis logam terkunci setelah ada riwayat. Enam tes Savings, pengujian upgrade sintetis 010→011, dan baseline init/reset lolos.

- Menambahkan Savings: tabungan uang, emas fisik berdasarkan gram/keping, dan deposito dengan informasi bunga tahunan opsional.
- CRUD milik pengguna, pilihan rekening sendiri dengan snapshot tersensor, estimasi emas menggunakan harga per gram manual, dan riwayat tambah/kurangi.
- Perubahan jumlah memakai Decimal, validasi tanggal berurutan, pencegahan saldo negatif, row lock, dan RequestId idempotent.
- Migration 010 menambahkan savings/saving_movements. Baseline 000 diperbarui sampai 010 dan reset mencakup kedua tabel baru; provider tetap dipertahankan.
- Migration 010 diterapkan lokal tanpa mengubah rekaman lama. Seluruh 59 tes backend dan pengujian baseline init/reset pada schema sintetis lolos.

### 2026-10-07

#### Autentikasi dan keamanan

- Login Google, JWT aplikasi, profil pengguna, dan pemeriksaan pengguna aktif.
- Semua endpoint keuangan membatasi akses ke data milik pengguna login; ID milik pengguna lain menghasilkan 404.
- Nomor rekening/kartu dienkripsi dengan AES-256-GCM dan nonce acak, dengan identitas akun/pemilik sebagai AAD. Respons hanya menyertakan nomor tersensor.
- Respons keuangan memakai `no-store`; error validasi tidak mengembalikan nilai input sensitif.

#### Tagihan

- CRUD akun Credit Card/Pay Later, platform dari database, serta tanggal tagihan/jatuh tempo opsional.
- Edit mempertahankan nomor kartu lama jika nomor baru tidak dikirim. Platform/tipe terkunci setelah akun memiliki transaksi.
- Hapus akun hanya diperbolehkan jika tidak memiliki transaksi atau seluruh tagihan lunas dan langganan sudah berhenti.
- Transaksi sekali bayar, cicilan, serta langganan bulanan dengan penghentian dan perubahan nominal untuk tagihan berikutnya.
- `TransactionDate` menentukan jadwal tagihan berdasarkan Billing Date/Due Date akun; tanggal 29–31 mengikuti akhir bulan jika diperlukan. Jadwal transaksi lama tetap dipertahankan.
- Pembayaran cicilan berurutan dan tidak dapat dibatalkan; nominal tagihan terakhir dapat diubah sebelum dilunasi.
- Rincian dan riwayat tagihan tersimpan di database; frontend membatasi tampilan riwayat lunas selama 3 bulan.

#### My Bank Account dan provider

- `billing_platforms` diganti menjadi `wallet_providers`, dengan `bank_f` bernilai 0/1. Tipe CREDIT_CARD/PAY_LATER hanya berada pada akun Tagihan.
- CRUD rekening debit, nomor rekening/kartu tersensor, Valid Thru, Admin Fee dan Others Fee bulanan. Nomor kartu dan Valid Thru wajib; biaya default Rp 0.
- Pilihan rekening debit hanya provider bank aktif, urut abjad. Platform Tagihan mencakup semua provider aktif, bank terlebih dahulu lalu abjad.
- Biaya rekening hanya dicatat; tidak otomatis memotong saldo atau memindahkan uang.

#### Hutang & Piutang

- CRUD catatan Hutang/Piutang, pembayaran sebagian/pelunasan, dan bunga opsional per bulan dari sisa pokok, tanpa bunga berbunga.
- Pembayaran melunasi bunga terbit terlebih dahulu, kemudian pokok; bunga berhenti setelah pokok lunas. RequestId mencegah pembayaran ganda.
- Piutang dapat mencatat Asal Dana dari rekening milik pengguna. Snapshot nama bank dan nomor tersensor tetap tersedia jika rekening dihapus.
- Tanggal Pengembalian dan cicilan fleksibel 1–60 kali; jadwal bulanan mengikuti tanggal cicilan pertama.
- Nominal pokok tiap cicilan dapat diubah dengan total tetap sama. Nominal cicilan yang sudah menerima pembayaran, termasuk sebagian, terkunci.
- Catatan lunas disembunyikan dari GET `/debts` setelah 3 bulan kalender sejak tanggal pembayaran pelunasan. Catatan aktif tetap tampil; data dan pembayaran tidak dihapus, dan detail tetap dapat dibaca oleh pemiliknya.
- `IsHistoryVisible` tersedia pada respons daftar/detail/mutasi. Batas riwayat dihitung dari data pembayaran yang ada, tanpa migration atau scheduler.
- Catatan yang memiliki pembayaran tidak dapat dihapus; syarat keuangan terkunci setelah pembayaran pertama.

#### Database

- Migration 001–009 mencakup akun Tagihan, transaksi/cicilan, langganan, Transaction Date, Hutang/Piutang, provider/rekening debit, serta sumber dana/rencana cicilan.
- `database/000_init.sql` merupakan baseline lengkap sampai 009. Database baru cukup menjalankan 000; database lama memakai migration yang belum diterapkan.
- Mode default `finance_tracker.reset = on` mengosongkan seluruh data aplikasi melalui TRUNCATE dan mempertahankan `wallet_providers`, termasuk provider custom. Mode `off` melakukan inisialisasi tanpa mengosongkan data.
- Seed 7 provider default ditambahkan tanpa menimpa data provider yang sudah ada. Script init/reset tidak dipakai untuk upgrade struktur lama.
- Perubahan batas riwayat 3 bulan hanya pada service/API; tidak menambahkan kolom atau tabel baru.

#### Verifikasi

- Tes backend mencakup ownership, validasi, enkripsi, pembayaran, langganan, jadwal tanggal, sumber rekening, dan perubahan nominal cicilan.
- Perubahan batas riwayat: 9 tes Hutang/Piutang dan 4 tes rencana cicilan lolos, termasuk batas akhir bulan serta retensi data sesudah disembunyikan.
- Init/reset diuji pada schema PostgreSQL acak dengan data sintetis; database aplikasi tidak di-reset oleh pengujian.
