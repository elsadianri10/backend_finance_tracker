# Langganan Pro — Midtrans

Implementasi 2 November 2026. Harga server: MONTHLY Rp29.000 dan ANNUAL Rp249.000. Tahunan hemat Rp99.000 (~28%) terhadap 12 pembayaran bulanan Rp348.000. Ini perbandingan paket, bukan diskon sementara. Pembatasan PDF dan slot aktif rutin/Split Bill kini berlaku; lihat [pengalaman Pro](pro-experience.md).

## Alur pengguna

Profil Saya menampilkan pilihan periode, pembayaran pertama sekarang, serta opsi perpanjangan otomatis (default tidak dicentang). Opsi otomatis memerlukan checkbox persetujuan terpisah. Server menyimpan versi persetujuan dan waktu persetujuan. Tidak ada auto-enrollment atau penagihan dari trial. Akun Pro gratis aktif dari admin tidak ditawari checkout; hak admin tetap terpisah dari Pro.

Snap menangani detail pembayaran; aplikasi tidak menerima atau menyimpan nomor kartu, CVV, PIN, atau token pembayaran pelanggan. Checkout manual memakai kanal merchant yang aktif; recurring dibatasi GoPay/kartu kredit. Token recurring hanya dipakai sementara di server untuk membuat jadwal; tidak disimpan atau diteruskan ke browser.

Pembayaran pertama langsung dilakukan saat checkout. Setelah status diverifikasi melalui API Midtrans, satu periode kalender ditambahkan setelah waktu pembayaran, sisa trial, atau masa Pro yang sudah dibayar (mana yang paling akhir). Contoh: trial berakhir 2 Desember, pembayaran bulanan terverifikasi 2 November → akses dibayar sampai 2 Januari; autodebit berikutnya mulai 2 Januari. Jadwal Midtrans memakai interval 1 bulan untuk bulanan dan 12 bulan untuk tahunan (API mendukung day/week/month). Bulan/tahun kalender, bukan selalu 30/365 hari; tanggal akhir bulan menyesuaikan kalender. Tidak ada diskon trial tersembunyi atau penagihan lagi tepat saat trial berakhir jika periode berbayar masih ada.

Perpanjangan dibuat setelah pembayaran pertama berhasil. GET status dari browser hanya meminta server memverifikasi status provider; callback browser tidak pernah menjadi bukti lunas. Payment dan Recurring Notification sama-sama harus dikonfigurasi. Recurring callback diverifikasi dengan GET Subscription dan GET Transaction, termasuk keanggotaan transaction_ids, nominal, mata uang, serta identitas langganan. Callback pending/deny tidak memberi akses. Duplikasi transaksi tidak menambah periode lagi. Full refund/chargeback menghapus kontribusi akses pembayaran tersebut dan meminta pembatalan recurring; partial refund tidak otomatis mencabut akses.

Pembatalan menggunakan Cancel Subscription, bukan Disable: cancel juga menghentikan retry tertunda. Akses yang sudah dibayar tetap sampai tanggal berakhir. Pembatalan tidak mengembalikan pembayaran yang sudah diproses. Percobaan ulang autodebit provider dinonaktifkan (retry max_interval 0); pembayaran gagal tidak memperpanjang akses. Masa Pro gratis/trial lain tetap mengikuti prioritas akses.

## Persiapan akun Midtrans

1. Buat akun merchant di https://dashboard.midtrans.com dan pilih Sandbox.
2. Minta Midtrans mengaktifkan kartu recurring/One Click, serta GoPay Tokenization, Recurring dan No PIN untuk kanal yang ingin digunakan. Aktivasi diperlukan juga untuk Sandbox. Jangan aktifkan flag recurring aplikasi sebelum kanal merchant siap.
3. Terapkan database/028_subscriptions.sql setelah 027. Migration hanya menambah dua tabel, tidak mengubah record keuangan. Jangan menjalankan baseline 000 pada database berisi data; default baseline mengosongkan data.
4. Isi environment berikut HANYA pada backend. Kunci dan token rahasia tidak dikirim ke chat, tidak dikomit dan tidak memakai NEXT_PUBLIC_.

```dotenv
MIDTRANS_ENABLED=true
MIDTRANS_ENVIRONMENT=sandbox
MIDTRANS_SERVER_KEY=<Sandbox Server Key dari Settings / Access Keys>
MIDTRANS_WEBHOOK_TOKEN=<secret acak URL-safe minimal 32 karakter>
MIDTRANS_RECURRING_ENABLED=true
SUBSCRIPTION_FRONTEND_URL=http://localhost:3000
```

Untuk deployment uji, FRONTEND_URL memakai origin HTTPS frontend tanpa path/query. Pastikan memakai backend/database pengujian yang terpisah; jangan menguji pembayaran Sandbox pada data produksi. Backend menolak Sandbox enabled saat VERCEL_ENV=production.

5. Di dashboard Midtrans → Settings → Payment/Configuration, isi **Payment Notification URL** dan **Recurring Notification URL** dengan URL backend yang sama:

```
https://<backend-domain>/subscriptions/webhooks/<MIDTRANS_WEBHOOK_TOKEN>
```

Secret URL perlu dirahasiakan dan direduksi dari log/monitoring yang dibagikan. Webhook dipanggil langsung ke backend, bukan frontend BFF yang memerlukan cookie sesi. Backend lokal memerlukan HTTPS tunnel untuk menerima callback Sandbox. Jangan menggunakan URL Production untuk uji Sandbox.

6. Restart/redeploy backend setelah environment diatur. Frontend hanya memerlukan API_BASE_URL backend yang benar; tidak ada Midtrans key di frontend.
7. Uji pembayaran berhasil/pending/gagal, GoPay/card recurring, pembayaran ganda, sisa trial, refund dan pembatalan di Sandbox. Bukti pengujian sesi implementasi ini memakai mock provider; pengujian langsung Sandbox masih memerlukan akun/kunci dan aktivasi merchant.
8. Setelah akun produksi disetujui dan kanal recurring aktif, gunakan Server Key produksi, mode production, origin frontend produksi dan kedua Notification URL produksi. Tinjau biaya serta kanal yang disetujui di kontrak/dashboard merchant sebelum menerima pembayaran. Tidak ada akun merchant dibuat atau transaksi produksi dilakukan otomatis oleh implementasi.

## API dan operasi

- GET /subscriptions/me: konfigurasi publik, harga, status pesanan milik akun (maksimal 10 terakhir), tanpa key/provider token.
- POST /subscriptions/checkout: RequestId UUID, Plan MONTHLY/ANNUAL, AutoRenew boolean, ConsentVersion 2026-11-02 jika otomatis. Nominal dari browser ditolak.
- POST /subscriptions/orders/{id}/refresh: verifikasi pembayaran awal dan rekonsiliasi hingga dua transaksi recurring yang belum tercatat per permintaan. Periksa lagi bila ada lebih banyak callback terlewat. Status readonly tidak menagih kembali.
- POST /subscriptions/orders/{id}/cancel-renewal: berhenti memperpanjang, tanpa mencabut periode yang sudah dibayar.
- POST /subscriptions/webhooks/{secret}: provider-only, body maksimal 32 KiB; verifikasi kembali melalui Basic-auth provider API. Jangan menaruh secret webhook pada frontend.

Lock row user menyelaraskan perubahan checkout/pembayaran/akses. RequestId dan transaction ID unik membuat retry idempotent. Identitas order disimpan sebelum permintaan eksternal. Jika pembuatan checkout/jadwal timeout, status REVIEW mencegah pembelian/jadwal baru yang bisa menggandakan tagihan. Jangan menghapus marker atau mengulang create-subscription manual setelah timeout. Callback creation dapat merekonsiliasi jadwal yang sudah dibuat; bila callback tidak tiba, admin perlu mencocokkan nama ftr_<order UUID tanpa dash> di dashboard Midtrans dan memakai script reconcile_subscription.py. Pembatalan yang belum dikonfirmasi tetap ditandai, tanpa mengaku sudah berhenti. Halaman Snap tanpa metode pembayaran menjadi EXPIRED setelah GET status 404 dan setidaknya 35 menit dari pembuatan (expiry Snap 30 menit).

Menonaktifkan MIDTRANS_ENABLED menghentikan komunikasi provider. Untuk pembatalan atau rekonsiliasi jadwal lama, aktifkan konfigurasi lingkungan merchant yang sesuai terlebih dahulu. Jangan menonaktifkan merchant sebelum seluruh jadwal aktif ditangani. Pergantian lingkungan dengan pesanan unresolved/recurring aktif ditolak untuk menghindari tagihan ganda.

## Verifikasi

- tests/test_subscriptions.py: SQLite in-memory dan mock Midtrans, tanpa pembayaran nyata.
- tests/check_subscription_migration.py dan tests/check_database_baseline.py: schema PostgreSQL acak, upgrade/repeat/data preservation serta reset sintetis.
- scripts/test-subscriptions.mjs di frontend: cookie sesi, origin, whitelist endpoint/field, URL checkout, 401/403.

Referensi resmi:
- https://docs.midtrans.com/docs/snap-snap-integration-guide
- https://docs.midtrans.com/reference/json-objects
- https://docs.midtrans.com/reference/gopay-tokenization-1
- https://docs.midtrans.com/reference/create-subscription
- https://docs.midtrans.com/reference/http-notification
- https://docs.midtrans.com/reference/cancel-subscription

Status lokal: migration 028 telah diterapkan dengan scripts/apply_subscription_migration.py --apply setelah backup privat dan perbandingan seluruh record lama; data lama identik. Database hosted Vercel/Neon belum dimigrasikan pada sesi ini.

Pemulihan setup ambigu (operator dengan akses backend, tidak menerima token pelanggan):

```powershell
.venv/Scripts/python.exe scripts/reconcile_subscription.py <order-uuid> <existing-midtrans-subscription-id>
.venv/Scripts/python.exe scripts/reconcile_subscription.py <order-uuid> <existing-midtrans-subscription-id> --apply
```

Default hanya memverifikasi identitas/nominal melalui Midtrans. --apply mencatat jadwal yang sudah ada dan menjalankan permintaan pembatalan yang tertunda, tanpa membuat jadwal atau tagihan baru. Jika dashboard memastikan tidak ada jadwal setelah timeout, jangan membuat jadwal baru melalui retry otomatis; operator perlu menutup kasus secara terkontrol sebelum mengizinkan checkout baru.

Verifikasi akhir sesi: 14 kasus pembayaran/adapter lolos (12 siklus pembayaran, 1 adapter HTTP, 1 refund recurring), 4 regresi trial lolos, proxy frontend subscription lolos, lint/TypeScript/build lolos, dan upgrade/baseline/reset sintetis lolos. Pengujian visual browser dan integrasi langsung ke Sandbox/Production belum dilakukan.

## Simulasi di dalam alur aplikasi (3 November 2026)

Gunakan aplikasi lokal melalui next dev dan login seperti biasa. Panel/tombol pengujian tidak ditampilkan pada Profil Saya atau Paket Pro normal. Untuk pengujian yang disengaja saja, URL /pro?simulate=1 mengaktifkan simulasi development dalam halaman Paket Pro yang sama, termasuk untuk akun Pro admin. Build produksi mengabaikan parameter simulasi.

Simulasi berjalan di komponen ProPlans yang sama: pilih bulanan/tahunan, coba checkbox autodebit dan contoh persetujuannya, lalu Tinjau pembelian. Dialog yang sama menampilkan paket, periode, total bayar dan ketentuan perpanjangan. Tombol Oke, lanjut bayar (simulasi) hanya menampilkan tahap selanjutnya. Handler berhenti sebelum API checkout dipanggil; data katalog simulasi tidak berisi pesanan akun asli dan seluruh aksi perubahan langganan diblokir selama simulasi.

Tidak dibuat order, transaksi pembayaran, aktivasi Pro, atau mandat autodebit. Paket akun, trial, Pro admin dan izin backend tetap asli. State simulasi hanya di memori komponen; Keluar simulasi mengembalikan tampilan normal. Refresh URL dengan simulate=1 sengaja mengaktifkan simulasi lagi; hapus parameter untuk membuka halaman normal. Halaman demo terpisah tidak lagi digunakan: URL lama /pro-simulation hanya mengarahkan ke /pro?simulate=1 pada development dan tetap 404 pada produksi/host non-loopback.

Simulasi tidak menggantikan pengujian Sandbox Midtrans. Pilihan bank/e-wallet/kartu provider baru dapat diuji setelah akun/kunci Sandbox dan kanal merchant aktif.

Checkout asli juga memakai dialog tinjauan yang sama. Order baru dibuat setelah pengguna memilih Oke, lanjut ke Midtrans; selanjutnya pengguna memilih metode pembayaran di provider. Frontend mengirim ExpectedAmount yang ditampilkan; backend memeriksa kesesuaiannya terhadap harga server sebelum membuat order. Field ini opsional untuk kompatibilitas, bukan sumber harga. Persetujuan autodebit tetap terpisah dan tidak dicentang secara default.

Ringkasan autodebit menampilkan estimasi tanggal penagihan berikutnya jika pembayaran berhasil hari ini. Estimasi memakai masa trial/Pro berbayar yang sudah tersedia pada frontend, memilih akhir masa akses yang paling jauh lalu menambahkan satu bulan atau satu tahun kalender dengan aturan UTC backend; tanggal ditampilkan dalam WIB. Sisa Pro gratis admin tidak dikonversi menjadi periode berbayar. Estimasi hanya informasi, tidak dikirim sebagai jadwal yang dipercaya server. Jadwal final tetap berasal dari pembayaran terverifikasi. Kasus akhir bulan/tahun kabisat dan carryover diuji melalui frontend scripts/test-subscription-estimate.mjs.


## Paket dan riwayat — 3 November 2026

GET /plans menyediakan aturan publik kanonis. GET /access/usage menyediakan jumlah aktif milik pengguna. Gratis 3 rekening/3 simpanan aktif; POST /bank-accounts/{id}/archive|restore dan /savings/{id}/archive|restore mengubah status tanpa mengubah saldo/ledger. Pemulihan tunduk pada batas slot. Migration 029 diperlukan.

GET /subscriptions/history?offset=0&limit=10 menyediakan pesanan milik pengguna pada lingkungan merchant aktif, total/NextOffset dan pembayaran terverifikasi beserta periode/refund. Limit maksimal 20; tetap dapat dibaca ketika gateway dinonaktifkan. Aksi pesanan terkini tetap ada pada /me. Persiapan publikasi, backup dan batas paket: release-readiness.md.


Pembaruan paket 3 November 2026: Tagihan dan Hutang/Piutang menjadi Pro, termasuk pembuatan, perubahan dan pembayaran melalui jalur Transaksi/Rutin. Pembacaan data lama serta operasi penghapusan yang sudah diizinkan tetap tersedia. Transaksi dan ekspor PDF/Excel transaksi tetap Gratis. Batas aktif rekening/Savings/rutin/Split Bill tidak berubah. Tidak memerlukan migrasi atau perubahan data keuangan.
