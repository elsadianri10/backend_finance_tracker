# CHANGELOGS
## BACKEND - FINANCE TRACKER

<be>
<br>

---

# Developer Changelogs:

## [v.1.0.0-Unrelease]
## 23 November 2026
### Tindak lanjut audit backend 6–7
- Ringkasan menghitung saldo Savings di database dan membaca rincian Tagihan yang belum lunas beserta nomor cicilan terakhir untuk proyeksi langganan.
- API Transaksi membaca kolom respons saja dan menyediakan filter bulan opsional.
- Log exception database menyertakan kategori dan SQLSTATE yang valid, dengan referensi yang sama seperti respons.

### Tindak lanjut audit backend 4–5
- Edit Transaksi memakai versi awal dari form. Simpan dengan versi lama ditolak dengan HTTP 409.
- Penghapusan Blob Wishlist memakai antrean yang disimpan di database. Jalankan `scripts/retry_wishlist_cleanup.py` untuk mencoba ulang pekerjaan yang masih tertunda.
- Migrasi 034 menambah versi transaksi dan tabel antrean tanpa mengubah nominal, tanggal, atau foto yang tersimpan.

### Tindak lanjut audit backend 1–3
- Pembayaran Tagihan lewat Transaksi atau Pengeluaran Rutin memakai tanggal yang dikirim, termasuk pada catatan Transaksi dan mutasi Savings.
- Baseline 000 mempertahankan data lama. Reset dipisahkan dan memerlukan konfirmasi database serta schema.
- Preflight memeriksa seluruh tabel dan kolom yang dipakai model serta constraint lama transfer. Kegagalan pemeriksaan skema menghasilkan kode keluar 1.

### Kategori Pindah Dana
- API Transaksi menerima kategori **Pindah Dana** untuk transfer biasa antar rekening sendiri.
- Ekspor PDF dan Excel menampilkan label Pindah Dana. Nilai transfer dikecualikan dari pemasukan dan pengeluaran. Tidak perlu migrasi database.

### Transfer internal dalam rekening yang sama
- Rekening sumber dan tujuan boleh sama pada Transaksi, alokasi Pengeluaran Rutin, dan penambahan Savings yang dicatat sebagai Transaksi.
- Tetap memeriksa kepemilikan rekening, mencegah mutasi Savings ganda pada pengiriman ulang, dan mengecualikan transfer dari pemasukan/pengeluaran.
- Diperlukan migrasi 033 untuk melepas pembatas rekening berbeda; data lama dipertahankan.

### Tanggal pembayaran cicilan
- Konfirmasi pembayaran Tagihan menyediakan tanggal pembayaran, default hari ini (WIB), terpisah dari jatuh tempo.
- Tanggal pilihan diterapkan ke status lunas, Transaksi, dan mutasi Savings; tanggal masa depan ditolak.
- Detail cicilan menampilkan tanggal pembayaran setelah lunas. Tidak memerlukan migrasi database atau perubahan data lama.

### Link berbagi Split Bill
- Link publik hanya-baca per grup: rincian pengeluaran, peserta, pembagian dan saran transfer tanpa login.
- Pemilik dapat membuat, mengganti, menyalin, atau mencabut link; link lama tidak berlaku setelah diganti/dicabut atau grup dihapus.
- Hash token disimpan di tabel relasional; diperlukan migrasi 032.

### 2026-11-14
- Koreksi ruang lingkup portal: /admin memiliki login dan sesi sendiri, tanpa tautan menu/tombol dari Finance Tracker. Cookie dan tujuan JWT admin/personal dipisahkan; backend memeriksa cakupan token pada setiap endpoint. Logout admin tidak mengeluarkan sesi personal dan sebaliknya. Google/passkey tetap dipakai, tidak memerlukan migrasi tambahan selain 031.

- Dashboard /admin terpisah dengan login Google/passkey kembali ke dashboard. Pengelolaan pengguna/Pro dan permintaan penghapusan dipindah dari Profil Saya. users.admin_f 0/1 menentukan hak admin, pemilik awal elsadianri10@gmail.com, penunjukan/pencabutan admin disertai audit dan proteksi pemilik/admin terakhir. Form serta API pengajuan hapus akun diblokir untuk admin. Migration 031 diperlukan; data keuangan dan paket Pro tetap dipertahankan.

### 2026-11-04

- Perbaikan hapus grup Split Bill pada PostgreSQL/Neon: rincian pembagian, item, pengeluaran, dan peserta dihapus sesuai urutan foreign key sebelum grup induk. Seluruh operasi memakai satu transaksi dan pemeriksaan pemilik. Tidak memerlukan migrasi database.

### 2026-11-03

- Persiapan pengguna umum: permintaan hapus akun di Profil Saya dan antrean tinjauan/pemrosesan admin dengan pemeriksaan pesanan, autodebit, retensi pembayaran serta retry pembersihan Blob. Pengingat stok/jatuh tempo di Ringkasan, referensi error dengan log teredaksi, modal responsif HP, backup PostgreSQL terenkripsi dan manifest penghapusan untuk restore terisolasi. Migration 030 diterapkan lokal dengan seluruh record lama identik; tidak ada akun nyata dihapus atau deploy produksi. Kebijakan publik tetap draft sampai identitas/kontak/retensi diputuskan.

- Koreksi pembagian paket: Tagihan dan Hutang/Piutang beserta sinkronisasi pembayarannya menjadi Pro. Gerbang service mencakup jalur pembayaran lintas Transaksi/Rutin; menu Gratis membuka pilihan paket, badge hanya setelah trial habis. PRO_REQUIRED tidak menghapus sesi. Transaksi termasuk PDF/Excel tetap Gratis, data lama dipertahankan. Tidak ada migrasi.

- Finalisasi paket: Gratis 3 rekening dan 3 simpanan aktif; penghitung pemakaian, arsip/pemulihan tanpa menghapus saldo/riwayat, serta tabel Gratis/Pro dari aturan server. Tagihan/Hutang mengikuti koreksi paket Pro di atas. Riwayat pembayaran langganan berpaginasi dilengkapi periode akses/refund. Halaman harga/bantuan dan draft kebijakan disiapkan; kebijakan produksi menunggu identitas/kontak serta persetujuan. Migration 029 dan restore backup diuji dengan schema sintetis; lokal dimigrasikan dengan data lama tetap identik, Neon belum diubah.

- Checkout menerima ExpectedAmount opsional untuk memverifikasi nominal yang sudah ditinjau pengguna. Jika harga berubah, permintaan ditolak sebelum membuat order eksternal. Tidak ada migrasi atau pembayaran produksi.

### 2026-11-02

- Revisi paket: seluruh Transaksi termasuk PDF/Excel tetap Gratis; Wishlist dan Stok Kebutuhan menjadi Pro dengan pemeriksaan server untuk pembuatan/pengelolaan. Data lama tidak dihapus; API baca, penghapusan/privasi, arsip kebutuhan, serta tautan dan reservasi Wishlist publik tetap dipertahankan. Tidak memerlukan migrasi.

- Pemeriksaan Pro pada server untuk ekspor PDF Transaksi/Split Bill, penambahan di atas 3 rencana rutin aktif dan 2 grup Split Bill aktif. Trial, Pro berbayar dan Pro gratis admin memperoleh akses Pro; Gratis tetap bisa ekspor Excel dan mengelola data lama, termasuk data yang sudah melebihi batas. Aktivasi kembali yang menambah slot ikut dibatasi. Tidak ada migrasi atau perubahan record lama; PRO_REQUIRED tidak diperlakukan sebagai sesi kedaluwarsa oleh frontend.


- Harga Pro Tahunan diperbarui menjadi Rp249.000; Pro Bulanan tetap Rp29.000. Penghematan tahunan Rp99.000 (sekitar 28%) dibanding 12 pembayaran bulanan. Harga berlaku untuk checkout baru; nominal pesanan/jadwal yang sudah dibuat tetap mengikuti snapshot masing-masing.

- Integrasi langganan Midtrans Snap dan Subscription API: harga server Rp29.000/bulan atau Rp250.000/tahun, checkout terautentikasi, consent autodebit GoPay/kartu kredit, verifikasi provider, perpanjangan kalender, sisa trial dipertahankan, pembatalan penagihan tanpa menghapus masa Pro berbayar, refund/chargeback, idempotensi serta rekonsiliasi webhook terlewat. Migration 028 hanya menambah subscription_orders/subscription_payments. Default pembayaran nonaktif; Sandbox langsung dan produksi masih memerlukan akun/kunci serta aktivasi kanal merchant. Petunjuk: docs/subscriptions.md.

- Migration 027 diterapkan pada database lokal setelah uji upgrade/repeat/baseline sintetis lolos, dengan backup dan perbandingan semua record: data keuangan, pengguna, Pro gratis, langganan dan audit lama tetap utuh.

- Trial Pro gratis 30 hari sekali per akun: migration 027 memberi trial akun lama sejak aktivasi; akun baru sejak login Google terverifikasi pertama. Tanggal dan sisa hari disediakan ke frontend. Login ulang, pengulangan migration dan perubahan Pro gratis tidak mengulang trial; Pro gratis/langganan aktif mengungguli trial dan tetap dipertahankan. Setelah expiry, status kembali ke sumber akses lain/Gratis. Tidak menambah penagihan otomatis atau pembatasan fitur baru. Uji auth/akses/trial dan migrasi/baseline pada schema sintetis lolos.

- Petunjuk aktivasi admin diperjelas: email Google admin di ACCESS_ADMIN_EMAILS backend; pengelolaan pengguna tersedia melalui Profil Saya. Penerima harus sudah terdaftar; akun Pro gratis tetap tidak mendapat wewenang admin.

- Dasar Paket & Akses: tabel relasional account_access/access_audit, status Gratis/Pro berlangganan/Pro gratis, pemberian atau pencabutan gratis oleh admin dengan tanggal opsional dan catatan riwayat. Admin ditentukan environment ACCESS_ADMIN_EMAILS dan terpisah dari Pro. Otorisasi server, pagination, optimistic version dan commit status/audit atomik; paid subscription tetap dipertahankan saat gift dicabut. Migration additive 026; belum mengaktifkan checkout atau pembatasan fitur.

### 2026-10-28

- Sumber Savings untuk pembayaran rutin, Tagihan, dan pembelian stok dengan pencatatan pengeluaran. PaymentInput/PurchaseInput menerima SavingId opsional; endpoint bayar Tagihan menerima body opsional SourceBankId/SavingId. Satu transaksi database mencatat ledger, progres pembayaran/stok dan mutasi REMOVE. Validasi pemilik/CASH/rekening/saldo/tanggal dan retry mencegah catatan ganda atau perubahan parsial. Pembayaran rutin yang terhubung ke utang/Tagihan tetap satu ledger. Undo rutin biasa membuat mutasi pengembalian; alokasi tabungan tetap memakai sumber rekening, bukan withdrawal Savings. Fingerprint stok tanpa SavingId mempertahankan kompatibilitas retry lama. Tidak perlu migrasi schema baru.

- Pembayaran utang dan pengembalian piutang dapat ditautkan ke Savings Tabungan Uang melalui SavingId opsional, dari menu Hutang & Piutang maupun Transaksi. Satu commit mencatat pembayaran, satu ledger, dan satu mutasi Savings (REMOVE/ADD), memakai relasi yang sudah ada tanpa migrasi baru. Validasi pemilik, jenis simpanan, rekening, saldo dan tanggal berlaku; kegagalan membatalkan seluruh perubahan. Pengiriman ulang tidak menggandakan catatan dan menolak perubahan target pada RequestId yang sama. Pembayaran lama tidak otomatis ditautkan ulang. Respons pembayaran menyertakan SavingUpdated agar frontend memuat ulang Savings hanya jika terpengaruh.

### 2026-10-27

- Stok Kebutuhan: override beli ulang per produk (jeda, lewati bulan berjalan sampai tanggal 1 bulan berikutnya, aktifkan lagi) pada kolom bertipe dengan default lama tetap aktif. Endpoint memeriksa pemilik/induk/versi/status arsip. Pengingat mengecualikan produk yang tidak eligible; kontrol induk tetap berlaku, stok/history/ledger tidak berubah. Migration additive 025 dan baseline terbaru; upgrade berulang pada data terisi diuji hanya di schema sintetis.

- Stok Kebutuhan: hapus permanen per produk yang diarsipkan, dengan pemeriksaan kepemilikan/versi/nama produk. Hanya produk dan riwayatnya dihapus; kebutuhan, produk lain dan seluruh transaksi keuangan tetap tersimpan. Tidak memerlukan migration baru. Verifikasi: tujuh tes stok dan cascade PostgreSQL pada schema sintetis lolos.

### 2026-10-26

- Stok Kebutuhan: DELETE hanya untuk kebutuhan yang diarsipkan, wajib konfirmasi nama persis dan versi data terbaru. Produk/stok/riwayat terhapus melalui FK cascade; seluruh transaksi keuangan tetap tersimpan. Kepemilikan, restore dari tab lain dan pelestarian ledger diuji; cascade diverifikasi di PostgreSQL schema sintetis. Tidak membutuhkan migration baru.

- Menu Stok Kebutuhan: kategori Kesehatan, Konsumsi, Beauty & Body Care; produk/brand andalan atau percobaan; stok per kemasan dipakai/cadangan; penggunaan kemasan, pengingat bulanan/stok menipis/manual, lewati bulan/jeda dan arsip. Riwayat pembelian/penyesuaian; pengeluaran opsional disimpan atomik dengan stok, pemeriksaan kepemilikan rekening, versi data dan retry idempotent. Tiga tabel relasional baru melalui migration additive 024; baseline/barrel exports diperbarui. Panduan docs/stock-needs.md. Verifikasi: 117 tes backend lolos; upgrade/baseline/reset dan konflik pembelian PostgreSQL diuji dalam schema sintetis, tanpa mengubah database aplikasi.

### 2026-10-17

- Wishlist mendukung upload foto JPG/PNG/WebP ke Vercel Blob private selain link, maksimal enam foto gabungan. Validasi isi/ukuran, konversi WebP tanpa metadata, simpan atomik, cleanup file, serta akses pemilik/link berbagi aktif dengan respons tanpa cache. Migration additive 023 menambah blob_url nullable; baseline diperbarui. Memerlukan store private dan BLOB_READ_WRITE_TOKEN di backend. Verifikasi: 112 tes backend lolos, termasuk upload/rollback/retensi foto/privasi dan adapter Blob tiruan. Upgrade berulang serta baseline/reset lolos hanya dalam schema sintetis; koneksi ke Blob asli belum diuji.

### 2026-10-16

- Wishlist: tujuh jenis daftar pribadi, grup/subtotal dan barang terpisah, prioritas/status, detail Holiday/kendaraan/gadget, serta beberapa URL foto. Link publik dapat dibuat/dicabut; reservasi wajib login, satu pemesan per barang, pembatalan hanya pemesan/pemilik, dan nama pemesan diproyeksikan hanya ke pemilik/pemesan. Route → controller → service, lima tabel relasional tanpa JSON/JSONB, migration additive 022 dan baseline terbaru. Upgrade/reset dan konflik reservasi PostgreSQL diverifikasi hanya dalam schema sintetis; data keuangan aplikasi tidak diubah. Verifikasi: 107 tes backend lolos; empat tes Wishlist mencakup CRUD/privasi/akses/status, dan PostgreSQL menguji upgrade, baseline/reset serta reservasi bersamaan.

### 2026-10-13

- Urutan PDF/Excel Transaksi: tanggal transaksi naik, lalu jam `created_at` dalam WIB naik untuk tanggal yang sama. Tanggal dari `created_at` tidak menggantikan tanggal transaksi; jika jam sama, urutan tabel dipertahankan. Tiga tes ekspor lolos, termasuk konversi UTC melewati tengah malam, tanggal pencatatan berbeda, jam sama dan konsistensi kedua format.

- Penyesuaian ekspor: PDF menjadi A4 portrait dengan kolom kategori/jenis dan rekening sumber/tujuan digabung agar tetap terbaca. PDF dan Excel diurutkan dari tanggal paling awal, mempertahankan urutan tabel untuk tanggal yang sama. Excel memakai pemasukan hijau, pengeluaran merah bernilai negatif, transfer netral, serta rumus/cache arus kas yang disesuaikan. Dua tes ekspor lolos mencakup tanggal, tanda nominal, warna, rumus dan nilai cache. PDF portrait tiga halaman dan Excel diperiksa secara visual; perubahan nominal pada salinan workbook juga diuji untuk memastikan rumus pengeluaran/arus kas menghitung ulang dengan benar. Data aplikasi tidak berubah.

- Tampilan PDF Transaksi: jenis dan nominal pemasukan berwarna hijau, pengeluaran merah dengan tanda minus, dan transfer netral. Ringkasan mengikuti warna pemasukan/pengeluaran serta arah arus kas bersih. Perubahan hanya pada tampilan PDF; nominal tersimpan dan perhitungan tidak berubah. Dua tes ekspor lolos dan empat halaman laporan sintetis diperiksa secara visual.
- Ekspor Transaksi: endpoint terautentikasi `POST /transactions/export/{pdf|xlsx}` menghasilkan laporan PDF dan Excel sesuai bulan, pencarian, jenis, rekening dan transaksi yang dipilih. Backend memvalidasi kepemilikan, status aktif serta filter sebelum membaca data; laporan memuat ringkasan, rincian transaksi, rekening tersensor dan catatan. PDF memakai A4 landscape dengan header tabel berulang; Excel menyimpan angka/tanggal asli, filter tabel dan rumus ringkasan dengan cache awal, serta memperlakukan input pengguna sebagai teks untuk mencegah formula injection. Tidak mengubah data atau membutuhkan migrasi/paket baru. Tes ekspor PDF/Excel dan validasi akses/filter lolos pada database sintetis.
- Koreksi tipe layanan ekspor: worksheet diperiksa sebelum digunakan, `PageSetupProperties` diinisialisasi eksplisit, dan referensi sel XML diperiksa terhadap `None` sebelum membaca cache rumus. Mengatasi diagnostik Pylance yang dilaporkan; kedua tes ekspor PDF/Excel lolos setelah perbaikan.

- Passkey wajib untuk seluruh akun: Google hanya menerbitkan sesi sementara pendaftaran/verifikasi, pendaftaran pertama terikat challenge sekali pakai selama 5 menit, dan API menolak sesi lama yang hanya memakai Google. Data keuangan dan schema database tetap utuh. Verifikasi: 102 tes backend sintetis lolos, termasuk pendaftaran wajib, penolakan sesi Google lama, ikatan challenge, replay, UV/origin/RP dan kedaluwarsa.

### 2026-10-12

- Keamanan Passkey: pendaftaran/penghapusan di Profil Saya, Google → sesi sementara → verifikasi WebAuthn wajib untuk akun aktif-passkey, dan kode pemulihan sekali pakai. Signature/origin/RP/UV/counter diverifikasi `webauthn==2.8.0`; challenge purpose-bound/sekali pakai/kedaluwarsa, lock dan pembatasan percobaan, HMAC kode pemulihan, serta versi sesi mencegah bypass Google/replay/sesi lama. Passkey terakhir dilindungi; perubahan keamanan memerlukan verifikasi baru. Migration 021 additive/relasional, baseline sampai 021, diterapkan pada database proyek dengan backup dan seluruh record lama identik. 96 tes backend lolos pada suite penuh, dan enam tes passkey final lolos termasuk signature rusak/verifikasi ulang dengan authenticator sintetis; upgrade dan init/reset hanya diuji di schema sintetis. Konfigurasi RP produksi memakai domain frontend yang diberikan pengguna; local memakai localhost. Belum mendaftarkan passkey pada perangkat fisik pengguna.

- Split Bill: diskon nominal per pengeluaran dibagi rata ke seluruh peserta grup dengan pembulatan rupiah tepat, setelah service charge/pajak. Potongan tampil di ringkasan, rincian bill dan PDF. Total Akhir Struk tetap menjadi total final, dengan penyesuaian setelah diskon; bobot negatif/nol ditangani dan saldo/transfer tetap seimbang. Migration 020 menambah kolom BIGINT `discount` dengan CHECK/default 0, tanpa JSON/JSONB; baseline sampai 020. Diterapkan pada database proyek dengan backup dan perbandingan semua record, tanpa reset. Verifikasi: 11 tes Split Bill lolos, upgrade/constraint/ORM dan baseline init/reset diuji dalam schema PostgreSQL sintetis, PDF contoh 20 peserta diperiksa secara visual.

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
