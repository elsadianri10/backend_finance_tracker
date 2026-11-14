# Paket dan akses pengguna

Tahap awal 2 November 2026: pengelolaan status Gratis/Pro dan pemberian Pro gratis. Trial Pro 30 hari otomatis tersedia setelah migration 027. Integrasi checkout/autodebit Midtrans dan harga Rp29.000/bulan atau Rp249.000/tahun telah ditambahkan melalui migration 028; pembayaran default nonaktif sampai konfigurasi serta aktivasi merchant selesai. Pembatasan PDF dan slot aktif rutin/Split Bill kini berlaku; lihat [pengalaman Pro](pro-experience.md). Lihat [panduan langganan](subscriptions.md). Tidak ada pengguna yang kehilangan akses ke data karena tahap ini.

## Menyiapkan admin

Database yang sudah sampai 030: jalankan database/031_user_admin_roles.sql sebelum memakai backend baru. Database yang lebih lama tetap perlu menjalankan migrasi yang belum ada secara berurutan. Jangan gunakan baseline 000 untuk upgrade database berisi data.

Hak admin berasal dari users.admin_f (0/1), bukan ACCESS_ADMIN_EMAILS. Migrasi memberi admin awal kepada akun elsadianri10@gmail.com yang sudah terdaftar; jika akun belum ada, pendaftaran Google terverifikasi pertama pada email tersebut membuatnya sebagai admin. Akun lain default 0. Pemilik utama tidak dapat dicabut lewat aplikasi. Admin lain dapat ditunjuk atau dicabut dari /admin, dan perubahan dicatat dalam user_admin_audit. Hak admin selalu diperiksa dari database pada setiap request; hak Pro tetap terpisah.

## Penggunaan

Buka Profil Saya, bagian Paket Anda. Pengguna melihat status akun sendiri. Admin membuka /admin untuk Kelola Akses Pengguna, pencarian akun terdaftar dan pagination 25 akun. Beri Pro Gratis atau ubah masa berlaku; tanggal di form mengikuti waktu perangkat dan dikirim sebagai UTC. Tanpa tanggal = tanpa batas waktu, sampai dicabut admin. Isi catatan perubahan. Akses Pro gratis berakhir tepat pada waktu yang dipilih tanpa cron; status dihitung saat request. Mencabut pemberian tidak membatalkan langganan Pro berbayar yang masih aktif. Jika tidak ada langganan aktif, status kembali Gratis. Data keuangan tidak dihapus.

Akun belum terdaftar harus login dahulu. Tidak ada undangan berdasarkan email yang belum terverifikasi. Riwayat hanya mencakup perubahan akses, dengan aktor, waktu, tindakan, tanggal berakhir, dan catatan; tidak menampilkan transaksi keuangan. Admin tidak dapat mengubah paid subscription lewat endpoint pemberian gratis. Status subscription_plan/subscription_until hanya diperbarui oleh pembayaran yang diverifikasi ke Midtrans; frontend tidak dapat menetapkan status Pro berbayar.

## API

- GET /access/me: status efektif sendiri dan IsAdmin.
- GET /admin/access/users?search=&offset=0&limit=25: akun dan status; maksimal 50 per halaman.
- PATCH /admin/access/users/{id}: Version, Action GRANT/REVOKE, ExpiresAt nullable, Reason wajib.
- GET /admin/access/users/{id}/history: maksimal 30 perubahan terakhir.

Semua endpoint admin memerlukan akun admin server. Versi awal akun tanpa record = 0. Perubahan mengunci row user, mengecek versi lalu menyimpan status/audit dalam satu commit. Versi stale ditolak 409, grant ke akun nonaktif ditolak. Expiry wajib timezone-aware dan masa depan. Proses ini tidak memberi hak admin baru. Proxy frontend membatasi path/method, origin perubahan, cookie sesi, ukuran body dan field respons; 403 admin tidak menghapus sesi login.

## Pengujian

tests/test_account_access.py memakai SQLite in-memory untuk otorisasi, revokasi, expiry, paid fallback, audit dan validasi. tests/check_access_migration.py memakai schema PostgreSQL acak untuk baseline/reset dan upgrade berisi data, tanpa reset database aplikasi. tests/check_database_baseline.py memeriksa kesesuaian ORM/baseline. Frontend scripts/test-account-access.mjs memakai API mock; pratinjau dengan --preview. Tidak ada perubahan pada database aplikasi saat verifikasi.

Status verifikasi diperbarui 2 November 2026: unit trial/akses/login SQLite, proxy, lint/TypeScript, build, serta pengujian upgrade/repeat/baseline/reset PostgreSQL sintetis lolos. Migration 027 telah diterapkan pada database lokal dengan backup dan perbandingan data. Pemeriksaan visual browser belum diverifikasi ulang.

Status paket pribadi tetap di Profil Saya; pengelolaan akses pengguna dan antrean penghapusan dipindah ke /admin. Tidak ada tautan Dashboard Admin di aplikasi umum. /admin menampilkan halaman login admin sendiri, lalu dashboard setelah Google/passkey berhasil. Cookie dan token sesi admin terpisah dari sesi Finance Tracker. Akun biasa mendapat penolakan akses di server. Form hapus akun tidak ditampilkan untuk admin dan pengajuan langsung melalui API juga ditolak. URL lama /account-access tetap mengarah ke /profile.


## Trial otomatis 30 hari (migration 027)

Akun yang sudah ada memperoleh satu trial 720 jam sejak migration 027 dijalankan. Akun baru memperoleh trial sejak login Google terverifikasi pertama. Trial disimpan di account_access.trial_started_at dan trial_until, bukan di browser. Login ulang, refresh, pemberian atau pencabutan Pro gratis, dan pengulangan migration tidak memperpanjang atau memulai ulang trial yang sudah tercatat. Perubahan masa berlaku trial tidak tersedia pada endpoint admin.

Urutan sumber akses: Pro gratis aktif dari admin, Pro berlangganan aktif, trial aktif, kemudian Gratis. Pro gratis tanpa batas waktu tetap berlaku setelah trial berakhir. Pencabutan Pro gratis masih dapat menyisakan trial/langganan aktif. Tepat pada trial_until, sumber TRIAL berhenti dan kembali ke sumber lain yang berlaku; tidak membutuhkan cron. Trial tidak memberi hak admin dan tidak menimbulkan tagihan otomatis.

Profil Saya dan daftar pengguna admin menampilkan Trial Pro gratis, tanggal mulai, tanggal berakhir dalam WIB, dan sisa hari (dibulatkan ke atas). Trial yang berakhir ditampilkan sebagai riwayat pada status Gratis. Profil memuat ulang status saat melewati batas trial bila halaman masih terbuka. Respons menambah TrialStartedAt, TrialEndsAt, TrialActive, TrialExpired, TrialDaysRemaining.

Jalankan hanya 027_account_trial.sql pada database yang sudah melalui 026, lalu deploy backend/frontend terbaru. Pengujian test_account_trial.py/test_account_access.py/test_auth.py memakai SQLite in-memory; check_trial_migration.py serta check_database_baseline.py/check_access_migration.py hanya schema PostgreSQL acak. Uji validasi, pengiriman field proxy dan build frontend sudah tersedia. Batas fitur Gratis/Pro tetap memerlukan tahap implementasi tersendiri; perubahan ini mengaktifkan masa trial dan status akses, belum mengunci fitur keuangan saat trial habis.

Aktivasi trial 027 pada database lokal 2 November 2026 selesai. Backup tersimpan di .migration-backups yang diabaikan Git; seluruh record keuangan, pengguna, Pro gratis, langganan dan audit lama dibandingkan sebelum/sesudah dan tetap identik. Aktivasi ini tidak menerapkan migration ke database Vercel/Neon terpisah.


## API peran admin — 14 November 2026

PATCH /admin/users/{id}/role menerima AdminF 0/1, ExpectedAdminF 0/1 dan Reason wajib. Hanya admin aktif dapat memakai endpoint. Akun nonaktif tidak dapat dipromosikan; pemilik utama dan admin aktif terakhir dilindungi. Update basi ditolak. Pencabutan berlaku untuk request berikutnya, termasuk sesi yang sudah login. GET /admin/users/{id}/role-history menampilkan riwayat peran kepada admin. Endpoint akses Pro tetap terpisah dan menunjuk admin tidak mengubah paket.

031 diuji upgrade/repeat/reset hanya di schema sintetis, data keuangan lama dipertahankan. Konfigurasi aplikasi saat implementasi menunjuk hosted; helper lokal menolak mengubah database tersebut. Migrasi database aplikasi belum diterapkan oleh sesi ini. Gunakan scripts/apply_admin_roles_migration.py --apply hanya pada database loopback; untuk hosted, review dan jalankan file SQL 031 sebelum deploy backend/frontend.


### Pemisahan portal dan sesi — 14 November 2026

Aplikasi umum di / dan login personal di /signin tetap khusus Finance Tracker. Portal /admin memiliki halaman Masuk Portal Admin dan dashboard sendiri pada URL yang sama. Menu/tombol Dashboard Admin di sidebar dan Profil Saya dihapus. Portal juga tidak menampilkan tautan ke keuangan pribadi.

Cookie finance_admin_session dan finance_admin_pending terpisah dari finance_session/finance_pending. JWT admin memakai tujuan admin_access serta admin_passkey_pending/admin_passkey_enrollment; backend menolak token personal pada endpoint pengelolaan dan menolak token admin pada API keuangan. Masuk/keluar biasa pada satu portal tidak mengubah sesi portal lain. Pemulihan kode atau perubahan keamanan akun tetap dapat mencabut seluruh sesi melalui auth_version bersama, sesuai perilaku keamanan akun.

Endpoint /admin/auth/google, /admin/auth/me dan /admin/auth/passkeys/* menangani login portal. Google terverifikasi dan passkey/recovery tetap digunakan. Login admin tidak memulai trial personal atau mendaftarkan akun biasa tanpa hak admin. RP/domain dan passkey akun tetap sama karena kedua portal berada pada domain yang sama. Tidak ada migrasi database tambahan di atas 031.
