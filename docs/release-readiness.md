# Persiapan peluncuran berbayar — 3 November 2026

## Yang sudah dibuat

- Kebijakan paket dari server: Gratis 3 rekening, 3 simpanan aktif, 3 rencana rutin aktif yang belum selesai, 2 grup Split Bill aktif sampai akhir tanggal WIB. Transaksi dan PDF/Excel transaksi, keamanan tetap Gratis; pengelolaan Tagihan dan Hutang/Piutang memerlukan Pro. Kelola Wishlist/Stok Kebutuhan dan PDF Split Bill memerlukan Pro. Akses membaca data lama tetap tersedia; reservasi hadiah pada Wishlist bersama tetap Gratis.
- Pemakaian slot di aplikasi dan arsip/pulihkan rekening/Savings. Arsip membebaskan slot, bukan menutup rekening. Saldo, link pembayaran, riwayat dan ringkasan tetap dipertahankan. Pemulihan ke atas batas Gratis perlu Pro. Tidak otomatis mengarsipkan data ketika trial/langganan berakhir.
- Riwayat pesanan berpaginasi dengan pembayaran terverifikasi, periode akses, refund, dan status pembatalan. Tidak menampilkan token provider. Tidak disebut sebagai faktur pajak atau bukti resmi merchant.
- Harga Rp29.000/bulan, Rp249.000/tahun; hemat Rp99.000 dibanding 12 bulan. Trial 30 hari sekali. Tidak ada penagihan trial otomatis.
- Halaman publik /pricing, /help, /privacy, /terms, /cancellation. Draft kebijakan hanya terlihat lokal. Produksi menampilkan status belum diterbitkan sampai semua pengaturan lengkap dan disetujui.

## Hal yang masih perlu diputuskan/disiapkan

Identitas pengelola dan kontak bantuan publik belum ditentukan pengguna. Tidak memakai email pribadi sebagai kontak otomatis. Aturan retensi, penghapusan akun (termasuk salinan backup), refund, lokasi pemrosesan dan dasar pemrosesan perlu disepakati/diperiksa sebelum publikasi. Draft bukan penilaian kepatuhan hukum.

Frontend .env.example menyediakan PUBLIC_OPERATOR_NAME, PUBLIC_SUPPORT_EMAIL, PUBLIC_RETENTION_POLICY, PUBLIC_DELETION_POLICY, PUBLIC_REFUND_POLICY dan PUBLIC_POLICIES_APPROVED. Hanya set approved=true setelah peninjauan dan kesiapan menjalankan kebijakan. Mengisi env tidak membuat proses penghapusan/refund otomatis.

Midtrans masih nonaktif tanpa merchant. Selesaikan aktivasi, kunci Sandbox, metode recurring yang disetujui, callback dan uji nyata Sandbox. Uji berhasil/pending/gagal, retry, refund, pembatalan, callback ganda/terlewat. Jangan menerima pembayaran produksi sebelum kebijakan dan bantuan siap. Lihat subscriptions.md.

## Migrasi dan verifikasi

029_plan_archives.sql bersifat tambahan dan berulang aman. Sudah diterapkan lokal dengan backup privat dan perbandingan seluruh kolom lama: identik. Neon produksi belum dimigrasikan. Terapkan migrasi berurutan yang belum ada setelah backup; jangan menjalankan 000_init.sql pada data aplikasi untuk upgrade/reset.

Jalankan `scripts/release_preflight.py` dengan konfigurasi database tujuan sebelum deploy. Pemeriksaan hanya membaca database dan mengembalikan kode keluar 1 jika tabel, kolom, atau aturan migrasi 033 belum cocok atau pemeriksaan database gagal. Hasil pada database lokal hanya berlaku untuk lingkungan lokal.

Setelah 033, jalankan migrasi 034 agar preflight menemukan versi Transaksi dan tabel cleanup Wishlist. Deploy backend dan frontend dalam rilis yang sama. Tab yang masih menjalankan frontend lama perlu dimuat ulang sebelum edit Transaksi karena API PATCH mewajibkan versi.

Tes akses, trial dan pembayaran memakai database sintetis/mock provider. Tes batas baru memeriksa 3 slot, archive/restore, data lama melebihi batas, semua sumber Pro, privasi serta paging riwayat. tests/check_plan_archive_migration.py dan check_database_baseline.py memakai schema acak. Tidak ada pembayaran nyata atau deploy otomatis.

## Backup dan pemulihan

Uji lokal tests/check_backup_restore.py berhasil: pg_dump custom pada schema sintetis acak, restore transaksional, seluruh record dan jumlah constraint identik. Schema aplikasi tidak direset/di-restore. Bukti ini memvalidasi prosedur lokal, bukan kemampuan pemulihan Neon produksi.

Sebelum rilis, tentukan RPO/RTO dan jadwal backup sesuai kebutuhan bisnis; jangan menjanjikan SLA yang belum diukur. Periksa history window/restore aktual pada paket Neon. Simpan backup terenkripsi dengan akses terbatas, retensi dan pembersihan sesuai kebijakan yang disepakati. Snapshot migrasi lokal bukan pengganti backup operasional penuh.

Untuk latihan produksi: buat backup database penuh lewat koneksi yang diotorisasi, simpan di lokasi privat; restore ke database/branch TERPISAH. Pastikan tidak ada webhook, worker atau callback pembayaran yang menagih dari lingkungan restore. Bandingkan jumlah record, saldo, relasi, constraint, ledger, akses dan riwayat langganan; ukur durasi restore. Tidak menjalankan reset/restore pada database aplikasi. Uji berkas gambar secara terpisah karena pg_dump tidak mencakup Vercel Blob.

Backup konfigurasi/rahasia secara terpisah di secret manager: ENCRYPTION_KEY diperlukan untuk kolom terenkripsi. Jangan menaruh kunci di dump publik atau Git. Perubahan domain/RP ID memengaruhi passkey. Simpan konfigurasi OAuth/origin dan merchant secara aman; lingkungan restore harus memblokir pembayaran keluar. Sebelum mengaktifkan kembali webhook/recurring setelah insiden, rekonsiliasi status merchant untuk menghindari tagihan ganda.

Referensi resmi:
- PostgreSQL dump/restore: https://www.postgresql.org/docs/current/backup-dump.html
- Neon history window: https://neon.com/docs/postgres/backup-restore/history-window
- Midtrans cancel subscription: https://docs.midtrans.com/reference/cancel-subscription
- UU Perlindungan Data Pribadi: https://jdih.komdigi.go.id/produk_hukum/view/id/832/t/crc32/


Pembaruan paket 3 November 2026: Tagihan dan Hutang/Piutang menjadi Pro, termasuk pembuatan, perubahan dan pembayaran melalui jalur Transaksi/Rutin. Pembacaan data lama serta operasi penghapusan yang sudah diizinkan tetap tersedia. Transaksi dan ekspor PDF/Excel transaksi tetap Gratis. Batas aktif rekening/Savings/rutin/Split Bill tidak berubah. Tidak memerlukan migrasi atau perubahan data keuangan.


## Implementasi kesiapan lanjutan — 3 November 2026

- Profil Saya menyediakan permintaan hapus akun dengan konfirmasi email, status, dan pembatalan sebelum diproses. Admin melihat antrean, memulai tinjauan, lalu mengetik nomor permintaan untuk pemrosesan permanen. Tidak ada akun nyata dihapus saat verifikasi.
- Service mengunci akun sebelum permintaan agar pembatalan tidak bersaing dengan pemrosesan. Akun admin harus dilepas wewenangnya dahulu. Pesanan yang belum selesai dan autodebit yang belum berhenti menghalangi penghapusan. Riwayat pembayaran berhasil/refund diblokir untuk tinjauan retensi; kebijakan retensi belum diputuskan, sehingga implementasi tidak menghapus bukti pembayaran secara otomatis.
- Data pribadi/keuangan akun dan reservasi hadiah miliknya dihapus dengan predicate kepemilikan. Data pengguna lain dipertahankan. Sesi lama menjadi tidak berlaku karena akun dihapus. Pendaftaran ulang nanti merupakan akun baru, bukan pemulihan data lama.
- Gambar upload masuk antrean pembersihan. Jika Blob gagal, status CLEANUP tetap tersimpan dan admin dapat mengulang. Status COMPLETED hanya diberikan setelah pembersihan gambar dikonfirmasi. Link gambar eksternal tidak dihapus dari situs pihak lain. Salinan backup bukan bagian penghapusan langsung.
- Permintaan selesai menyimpan UUID subjek dan waktu untuk pencegahan pemulihan data yang telah dihapus; tidak menyimpan nama/email setelah akun dihapus. Retensi manifest ini masih perlu ditentukan dalam kebijakan final.
- Migration 030 menambah account_deletions dan account_deletion_blobs. Upgrade/repeat dan baseline/reset lulus di schema sintetis. Diterapkan lokal dengan backup privat dan perbandingan semua record lama: identik. Neon belum dimigrasikan.
- Ringkasan menampilkan pengingat jatuh tempo sampai H+7, termasuk yang lewat, serta stok habis/belanja ulang. Tanggal mengikuti WIB. Jeda/lewati/arsip produk mengikuti kelayakan pengingat; Tagihan/Hutang/Stok ditampilkan pada Pro. Ini pengingat di aplikasi, bukan email/push terjadwal.
- Modal umum dibatasi tinggi viewport dinamis dan dapat digulir. Chrome headless pada akun/backend sintetis memeriksa profil Gratis/trial/Pro berbayar/Pro admin, alur permintaan/batal hapus, panel pengingat dan modal tinjauan pembelian. Lebar 390px dan pengingat 320px tidak meluber horizontal. Tidak ada checkout dikonfirmasi. Artefak lokal di frontend .qa-artifacts/release-mobile.

## Error dan observabilitas

Backend menambahkan X-Request-ID. Error tak tertangani mengembalikan pesan umum dan referensi; log terstruktur hanya memuat template rute (bukan nilai path/query), metode, status/durasi, referensi, serta tipe exception. Tidak mencatat isi transaksi, cookie, token, credential atau pesan exception mentah. Request lambat >=2 detik dan respons 5xx masuk log.

Frontend memiliki error boundary dengan tombol coba lagi dan referensi. POST /api/diagnostics memakai same-origin, batas body dan batas 60 laporan/menit per instance; hanya menerima kode render_error, UUID referensi dan digest yang dibatasi. Tidak meneruskan message/stack atau state aplikasi. Log ini berada pada runtime aplikasi/Vercel, bukan dikirim ke layanan analitik pihak ketiga. Batas per instance bukan rate-limit global. Error yang sudah ditangani dalam form tetap menampilkan pesan form.

Filter runtime logs berdasarkan request_failed/request_result/client_error dan referensi. Atur retensi, akses log, serta alert 5xx/latensi melalui fasilitas hosting setelah pengelola dan kontak dipilih. Belum ada email/SMS/alert ke pihak lain yang diaktifkan.

Gunakan nilai `X-Request-ID` dari respons untuk mencari kedua event backend. Untuk exception database, `request_failed` menambahkan `category` dan menyertakan `sqlstate` bila kode driver valid. Kode `42P01` berarti tabel hilang dan `42703` berarti kolom hilang. Keduanya dapat diperiksa dengan preflight terhadap database tujuan. Statement SQL, parameter, maupun pesan driver tidak dicatat. Respons 5xx yang sudah ditangani tanpa exception tetap muncul di `request_result`.

## Backup terenkripsi dan restore setelah penghapusan

scripts/backup_database.py membuat custom dump pg_dump yang dienkripsi AES-256-GCM. BACKUP_ENCRYPTION_KEY harus merupakan kunci hex 32 byte TERPISAH dari ENCRYPTION_KEY aplikasi dan disimpan di secret manager, bukan bersama berkas backup atau Git. Contoh lokal: .venv/Scripts/python.exe scripts/backup_database.py --output .database-backups/finance-YYYYMMDD.ftbackup. Hosted memerlukan --allow-hosted. Tidak menerima kunci pada argumen CLI, tidak menimpa backup, dan tidak melakukan restore. Temporary plaintext dump dibersihkan setelah selesai. Klien pg_dump harus kompatibel dengan server.

Tes menguji round-trip enkripsi, penolakan kunci salah/berkas berubah. tests/check_backup_restore.py menguji custom dump/restore data sintetis terpisah. Backup produksi terenkripsi dan latihan restore Neon aktual belum dijalankan; kunci, jadwal, retensi, RPO/RTO serta penyimpanan privat belum dikonfigurasi.

Sebelum restore, ekspor manifest penghapusan TERBARU dari database aktif ke tempat privat terpisah: scripts/export_deletion_manifest.py --output <nama>.deletion-manifest.csv. Berkas hanya berisi UUID/status/waktu. Restore selalu ke database/branch terisolasi tanpa webhook/worker pembayaran. Terapkan kembali semua penghapusan dalam manifest dan periksa pembersihan Blob sebelum akses diaktifkan agar backup lama tidak menghidupkan kembali data yang sudah dihapus. Jangan menganggap keberhasilan decrypt sama dengan keberhasilan restore database.

## Hasil pemeriksaan Vercel baca-saja

3 November 2026: frontend /signin dan backend /version merespons 200. Frontend /pricing dan /help serta backend /plans masih 404 pada domain produksi yang diberikan. Ini tidak membuktikan masalah autentikasi; versi yang aktif belum menyediakan rute tersebut. Tidak ada deploy atau perubahan konfigurasi Vercel/Neon dilakukan. Uji Google/passkey, sesi habis, upload Blob, callback merchant dan paket pada deployment baru masih diperlukan setelah deploy dan migrasi yang ditinjau.


## Dashboard admin — 14 November 2026

/admin adalah halaman pengelolaan terpisah dari keuangan pribadi. Pengelolaan Pro gratis dan permintaan penghapusan dipindahkan dari Profil Saya. users.admin_f menjadi sumber hak admin; ACCESS_ADMIN_EMAILS tidak lagi memberi akses. Admin dapat menunjuk/mencabut admin lain, perubahan diaudit, dan hak Pro tidak otomatis berubah. Pemilik utama elsadianri10@gmail.com dilindungi. Form hapus akun disembunyikan serta pengajuan API ditolak untuk admin.

Migration 031_user_admin_roles.sql diperlukan sebelum backend baru. Skrip menambah kolom dan audit relasional, memberi flag 1 hanya kepada email pemilik utama, mempertahankan admin lain saat diulang serta tidak mengubah data keuangan. Tes migrasi/baseline memakai schema sintetis. Database aplikasi kini menunjuk hosted dan belum dimigrasikan dalam sesi ini; helper lokal sengaja menolak hosted. Hak admin lama berbasis environment tidak berlaku setelah deploy kode baru.


### Pemisahan portal dan sesi — 14 November 2026

Aplikasi umum di / dan login personal di /signin tetap khusus Finance Tracker. Portal /admin memiliki halaman Masuk Portal Admin dan dashboard sendiri pada URL yang sama. Menu/tombol Dashboard Admin di sidebar dan Profil Saya dihapus. Portal juga tidak menampilkan tautan ke keuangan pribadi.

Cookie finance_admin_session dan finance_admin_pending terpisah dari finance_session/finance_pending. JWT admin memakai tujuan admin_access serta admin_passkey_pending/admin_passkey_enrollment; backend menolak token personal pada endpoint pengelolaan dan menolak token admin pada API keuangan. Masuk/keluar biasa pada satu portal tidak mengubah sesi portal lain. Pemulihan kode atau perubahan keamanan akun tetap dapat mencabut seluruh sesi melalui auth_version bersama, sesuai perilaku keamanan akun.

Endpoint /admin/auth/google, /admin/auth/me dan /admin/auth/passkeys/* menangani login portal. Google terverifikasi dan passkey/recovery tetap digunakan. Login admin tidak memulai trial personal atau mendaftarkan akun biasa tanpa hak admin. RP/domain dan passkey akun tetap sama karena kedua portal berada pada domain yang sama. Tidak ada migrasi database tambahan di atas 031.
