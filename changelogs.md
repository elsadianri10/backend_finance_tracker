# CHANGELOGS
## BACKEND - FINANCE TRACKER

<be>
<br>

---


# Developer Changelogs:

## [v.1.0.0-Unrelease]

### 2026-10-09

- Split Bill relasional: migration 015 menyalin dokumen lama ke grup/peserta/pengeluaran/item/shares dengan kolom bertipe, composite FK, CHECK dan posisi urutan; menghapus kolom document. API/PDF dan kalkulasi tetap sama, PATCH atomic/versioned, pembacaan memakai shared lock. Baseline 000 diperbarui sampai 015. Dua grup lokal sudah dimigrasikan tanpa reset, dengan backup di folder lokal yang diabaikan Git; semua field/urutan/metadata/perhitungan/transfer identik. Preferensi fitur baru tanpa JSON/JSONB dicatat di AGENTS.md.
- Verifikasi relasional: 71 tes backend lolos, termasuk 8 tes Split Bill. Upgrade PostgreSQL sintetis memeriksa rollback backfill gagal, composite FK lintas grup, CRUD/cascade, serta data/order/kalkulasi identik; baseline init/reset diuji hanya di schema sintetis. Default biaya kosong diperbaiki menjadi Decimal(0) agar field service charge/pajak yang tidak dikirim tetap valid.

- PDF Split Bill: semua judul kolom memakai font bold, termasuk ringkasan peserta, rincian biaya, saran transfer, item, dan pembagian per bill. Header berulang di halaman lanjutan memakai gaya yang sama; hasil diperiksa melalui PDF sintetis.

- Koreksi urutan PDF: bill mengikuti Tanggal Pengeluaran (terlama dahulu, stabil untuk tanggal sama). Urutan nama peserta dan item bersama paling akhir hanya di dalam masing-masing bill.

- PDF Split Bill: tambahan jarak sebelum Daftar Pengeluaran / Transaksi; tabel peserta dan nama penerima diurutkan abjad. Bill/item berdasarkan penerima dengan semua peserta di akhir. Urutan hanya untuk ekspor, tanpa perubahan kalkulasi atau data tersimpan. Tes backend dan PDF sintetis Elsa/Nata/bersama lolos.

- PDF Split Bill menjadi A4 portrait, ringkasan peserta/rincian biaya dipecah menjadi tabel yang sesuai lebar halaman. Subjudul Daftar Pengeluaran / Transaksi ditambahkan sebelum bill pertama. Contoh 2 peserta tetap satu halaman, tes backend serta render grup 20 peserta diperiksa.

- PDF Split Bill: rincian bill mengalir tanpa pemisah halaman wajib, spacing dirapatkan tanpa mengecilkan teks tabel. Contoh Ramen YA 2 peserta muat satu halaman; contoh 20 peserta/2 bill tetap terbaca dengan pergantian halaman otomatis. Tes backend dan render PDF diperiksa.

- Split Bill: tombol Export PDF per grup; PDF A4 landscape berisi ringkasan peserta, saran transfer, detail pengeluaran dan penyesuaian struk. Endpoint/proxy milik user, JWT server, no-store; dependency backend ReportLab. Tes backend termasuk ownership ekspor, proxy unduhan PDF, lint dan build lolos. Tata letak 20 peserta diperiksa lewat render PDF sintetis di preview/.

- Split Bill: Total Akhir Struk opsional, selisih proporsional dan baris Penyesuaian Struk. Total pembayaran serta saran transfer mengikuti nominal akhir; data lama tanpa field tetap sama. Tersimpan dalam JSONB tanpa migration tambahan. Tujuh tes backend termasuk contoh Rp 177.021 ke Rp 177.000, penyesuaian positif/negatif/nol dan validasi nominal.

- Split Bill: default service charge rata ke semua peserta; pajak mengikuti konsumsi + bagian service charge. Mode MIXED ditambahkan tanpa mengubah kalkulasi pengeluaran lama, dengan 6 tes backend termasuk peserta tanpa konsumsi dan pembulatan nominal.

- Verifikasi Split Bill: 5 tes backend, migration 014 dengan data lama tetap utuh, baseline init/reset sintetis, lint, production build, dan tes proxy 20 peserta lolos. Form simpan dan ringkasan transfer diperiksa melalui preview sintetis empat peserta; screenshot di preview/split-bill-preview.png dan preview/split-bill-form.png pada proyek frontend.

- Split Bill Calculator: grup 2–20 peserta, banyak pengeluaran, pembagian item rata/custom, biaya nominal/persen, pajak dengan opsi service charge, pembulatan rupiah tepat, ringkasan peserta dan saran transfer saldo gabungan. CRUD milik user, optimistic Version, migration 014 tanpa reset; baseline 000 sampai 014.

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
