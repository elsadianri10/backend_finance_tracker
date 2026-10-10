# CHANGELOGS
## BACKEND - FINANCE TRACKER

<be>
<br>

---


# Developer Changelogs:

## [v.1.0.0-Unrelease]

### 2026-10-10

- Hutang/Piutang relasional: JSON `debts.installment_amounts` dipindahkan ke `debt_installments` dengan FK, primary key `(debt_id, sequence)`, nominal NUMERIC dan constraint urutan/nominal. API serta perhitungan tetap sama; ORM memuat cicilan secara berkelompok. Migration 019 memvalidasi data lama, memeriksa backfill, lalu menghapus kolom JSON secara atomik. Diterapkan ke database proyek dengan backup lokal di `.migration-backups`; seluruh record lama serta nominal/urutan cicilan identik dan schema aplikasi tidak lagi memiliki kolom JSON/JSONB. Baseline sampai 019. Verifikasi: 27 tes Hutang/Piutang, cicilan, sinkronisasi pembayaran, rutin dan Ringkasan lolos; upgrade/rollback invalid-data dan pembacaan saldo PostgreSQL diuji pada schema sintetis, serta init/reset sintetis mempertahankan dan mengosongkan rincian cicilan dengan benar. Database aplikasi tidak direset.
- Koreksi tipe schema rekening: default `account_number` untuk edit memakai string kosong sesuai anotasi `str`, mengatasi Pylance `reportAssignmentType`. Field yang tidak dikirim tetap mempertahankan nomor tersimpan melalui `model_fields_set`; nomor kosong/null yang dikirim eksplisit tetap ditolak. Card Number dan Valid Thru tetap opsional.
- Gaya penulisan route: seluruh 55 endpoint memakai decorator `@router.get`, `@router.post`, `@router.patch`, atau `@router.delete`, sesuai kebiasaan proyek. Route meneruskan parameter ke controller; aturan bisnis tetap di service. Kontrak OpenAPI identik dengan pendaftaran langsung ke controller. Route versi juga disesuaikan agar memanggil `get_version` yang tersedia. Preferensi decorator dicatat di AGENTS.md; tidak ada perubahan skema atau data.
- Verifikasi decorator: dari 89 tes backend, 88 lolos pada pengujian penuh; satu tes sinkronisasi diperbaiki agar mencari ledger lewat ID pembayaran, bukan mengasumsikan urutan transaksi dengan timestamp sama. Kelima tes sinkronisasi pembayaran kemudian lolos saat dijalankan ulang, memakai database sintetis.
- Kelengkapan package: ekspor `__init__.py` controllers, services, routes, models, schemas, dan helpers diperbarui sesuai modul aktif; seluruh router diimpor lewat package pada entrypoint. Modul controller/service/schema/helper dimuat saat diperlukan untuk menghindari impor melingkar dan mempertahankan alias publik yang sudah ada. Tidak ada perubahan endpoint atau data.
- Konsistensi struktur API: handler Hutang & Piutang, My Bank Account, Savings, Split Bill, Pengeluaran Rutin/Transaksi, dan Ringkasan dipindahkan dari route ke controller. Route hanya mendaftarkan endpoint; controller menangani request/response dan memanggil service. Handler profil autentikasi serta respons versi juga ditempatkan di controller; operasi hapus grup Split Bill berada di service. URL, metode HTTP, validasi, autentikasi, status, header dan bentuk respons dipertahankan; tidak ada perubahan skema atau migrasi data. Verifikasi: 89 tes backend dan 8 tes Split Bill setelah pemindahan operasi hapus lolos; kontrak OpenAPI enam modul identik, seluruh 55 handler berasal dari controller, dan autentikasi endpoint keuangan tetap terpasang.
- Koreksi tipe pemuatan rutin pada Ringkasan: parameter dan hasil `list_plans` diberi anotasi eksplisit sebagai fungsi async yang menghasilkan daftar rencana. Pemanggilan tetap memakai `await` karena fungsi membaca database secara async; hasil perhitungan tidak berubah.
- Koreksi tipe Ringkasan Keuangan: dictionary aset dianotasi menerima `int | float`, sesuai nominal/jumlah bulat dan berat logam desimal. Mengatasi diagnostik Pylance pada penjumlahan gram tanpa mengubah perhitungan atau data tersimpan.
- Koreksi tipe sinkronisasi Savings: model pergerakan saldo dan pembatalannya dibuat lewat `MovementCreate.model_validate` dengan alias PascalCase, mengatasi diagnostik konstruktor Pylance. Validasi, pencatatan sekali, dan aturan saldo tetap sama. Tes pembatalan/pembayaran ulang memakai tanggal contoh tetap agar tidak bergantung pada tanggal mesin.
- Koreksi tipe Pengeluaran Rutin: helper validasi memakai `NoReturn` agar akses Tagihan setelah validasi tidak dianggap opsional. Model pembayaran internal dibuat lewat `model_validate` dengan alias PascalCase, mengatasi diagnostik parameter konstruktor Pylance tanpa melonggarkan validasi API atau mengubah data.
- Koreksi tipe Hutang & Piutang: helper validasi `invalid` diberi tipe hasil `NoReturn` karena selalu melempar error. Pylance dapat memastikan rekening bukan `None` setelah validasi kepemilikan; perilaku validasi dan pencatatan tetap sama.
- Koreksi tipe jadwal Tagihan: tanggal opsional dan hari tagihan/jatuh tempo diperiksa sebelum perhitungan, sehingga diagnostik Pylance terkait `None` teratasi. Helper langganan diberi tipe model/tanggal yang eksplisit; aturan jadwal dan data tersimpan tetap dipertahankan.
- Koreksi tipe autentikasi: hasil `verify_google_token` dianotasi sebagai `Mapping[str, Any]`, sesuai tipe hasil verifier Google, untuk mengatasi diagnostik Pylance `reportReturnType`. Perilaku verifikasi token dan login tetap sama.
- Optimasi Ringkasan Keuangan: total dan jumlah transaksi bulanan dihitung lewat satu agregasi SQL, tanpa memuat seluruh objek ledger. Filter pemilik, periode, transaksi aktif, dan pengecualian tarik tunai/pengembalian piutang dari pendapatan tetap dipertahankan.
- Optimasi pilihan pembayaran: urutan cicilan terakhir seluruh langganan dibaca dalam satu query berkelompok, menggantikan query per langganan. Pembuatan jadwal tetap memakai lock dan transaksi yang sama. Pembayaran rutin dikelompokkan sekali per rencana untuk mengurangi pemrosesan berulang saat menyusun respons.
- Deployment: konfigurasi Vercel backend menetapkan region fungsi `sin1` (Singapore), sesuai lokasi Neon. Berlaku setelah redeploy backend; tidak memindahkan database. Kecepatan deployment belum diukur.
- Verifikasi: 5 tes Pengeluaran Rutin, 4 tes Ringkasan Keuangan, dan integrasi proxy dengan data sintetis lolos. Tes memastikan jumlah query pilihan pembayaran tetap sama ketika jumlah langganan bertambah dari 1 menjadi 5. Tidak ada migrasi, reset, atau perubahan data pengguna.

### 2026-10-09

- Pembayaran dua arah: Transaksi dapat membayar Tagihan, Hutang/Piutang, atau siklus rutin; konfirmasi dari menu asal membuat satu ledger dan memperbarui progres rencana aktif tertaut. Tanggal Tagihan mengikuti waktu konfirmasi UTC+7. Kepemilikan, nominal/jadwal, lock per pengguna, RequestId/hash, FK dan indeks unik mencegah pembayaran ganda; semua perubahan commit bersama. Migration 017 diterapkan tanpa reset/backfill dan seluruh data lama identik. Baseline sampai 017. Verifikasi: 81 tes backend, upgrade/baseline PostgreSQL sintetis, proxy, lint, build, form Tagihan dan penerimaan Piutang.

- Kategori Transaksi: entertainment, education, donation, debt, bonus, investment ditambahkan ke validasi create/update/import. Kategori lama tetap didukung; tidak memerlukan migration database.

- Transaksi menerima kategori top_up (Top Up); validasi nominal rencana aktif memakai pesan “Nominal aktif harus lebih dari 0 (nol)”. Tidak memerlukan perubahan skema database.

- Pengeluaran Rutin: Langganan, Setoran per penerima/komponen, alokasi rekening sendiri, status aktif/catatan/berhenti/selesai, interval 1–12 bulan, dan cicilan sampai 60 kali. Progres awal dapat dicatat tanpa membuat transaksi historis; pembayaran aktual menambah progres dan ledger secara atomik. Pembatalan hanya pembayaran terakhir, dengan audit void dan pencatatan ulang yang aman. Tagihan tertaut memakai installment yang sudah dibayar serta mencegah ledger ganda.
- Transaksi: ledger milik pengguna untuk pemasukan/pengeluaran/transfer, rekening sumber/tujuan dengan label tersamarkan, CRUD, dan impor satu kali catatan browser. Migration 016 diterapkan lokal tanpa reset: seluruh record/tabel sebelumnya identik dan empat tabel baru kosong; tanpa JSON/JSONB. Baseline 000 sampai 016. Verifikasi: 76 tes backend, upgrade PostgreSQL sintetis termasuk undo/repaid, baseline init/reset, proxy FE, lint, TypeScript, build, dan preview sintetis.

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
