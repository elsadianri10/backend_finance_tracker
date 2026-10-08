# CHANGELOGS
## BACKEND - FINANCE TRACKER

<be>
<br>

---


# Developer Changelogs:

## [v.1.0.0-Unrelease]

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
