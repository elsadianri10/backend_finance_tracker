# Penanda, promosi dan pengingat Pro

Disetujui 2 November 2026: menu dasar tetap terbuka; halaman harga hanya ditampilkan saat pengguna memilih fitur Pro yang tidak tercakup paketnya. Halaman harga /pro memakai checkout dan persetujuan autodebit yang sama dengan Profil Saya. Harga bulanan Rp29.000, tahunan Rp249.000 (hemat Rp99.000 dibanding 12 pembayaran bulanan).

Sidebar: Pengeluaran Rutin, Tagihan, Hutang/Piutang, Savings, Wishlist, Stok Kebutuhan, Split Bill dan My Bank Account memiliki penanda cakupan Pro. Badge hanya tampil jika EffectivePlan FREE dan TrialExpired true; akun yang statusnya belum dimuat, trial aktif, Pro berbayar dan Pro gratis admin tidak melihat badge. Transaksi tidak diberi badge Pro dan seluruh fitur/ekspornya tetap Gratis. Angka batas bank/Savings belum ditetapkan, sehingga tidak diada-adakan. Sinkronisasi pembayaran lama tetap berfungsi; perubahan ini tidak memutus relasi pembayaran atau menonaktifkan data yang sudah ada.

Pemeriksaan server yang diaktifkan:
- Transaksi termasuk ekspor PDF dan Excel tetap Gratis. PDF Split Bill memerlukan Pro.
- Wishlist dan Stok Kebutuhan menjadi fitur Pro: pemilik dengan trial/Pro aktif dapat membuat dan mengelola datanya. Akun tanpa Pro yang membuka menu melihat halaman harga; pemeriksaan tulis juga dilakukan server. Data lama tidak dihapus; API baca dan operasi penghapusan/privasi yang relevan dipertahankan. Arsip kebutuhan tetap dapat dilakukan agar kebutuhan dapat dihapus tanpa membeli Pro.
- Tautan Wishlist yang sudah dibagikan tetap dapat dibuka publik. Pengguna Gratis yang login tetap boleh reservasi hadiah melalui tautan berbagi; tidak perlu berlangganan hanya untuk membelikan hadiah.
- Gratis maksimal 3 rencana rutin aktif yang belum selesai. Catatan/berhenti/selesai tidak dihitung. Rencana lama di atas batas tetap bisa dibaca, dibayar, diedit dan dikurangi; menambah rencana aktif atau mengaktifkan kembali yang sebelumnya tidak aktif memerlukan Pro jika batas tercapai.
- Gratis maksimal 2 grup Split Bill aktif (tanggal akhir belum lewat menurut Asia/Jakarta). Riwayat tidak dihitung; data lama tetap bisa dibaca/diedit. Grup baru atau perubahan riwayat menjadi aktif yang menambah slot diperiksa di server.
- Trial Pro, langganan Pro aktif, dan Pro gratis admin aktif memenuhi pemeriksaan yang sama. Pemeriksaan masa berlaku tetap dari backend; UI bukan pengaman tunggal. Penolakan PRO_REQUIRED mengarahkan ke /pro tanpa logout.

Promosi login:
- Marker hanya dibuat setelah login Google penuh berhasil atau langkah passkey/enrollment/recovery selesai. Tidak dibuat pada login Google yang masih menunggu passkey, sesi yang masih aktif, refresh halaman atau navigasi.
- Marker dikonsumsi satu kali setelah status akses berhasil dimuat. Refresh/navigasi tidak memunculkannya kembali; login berhasil berikutnya membuat marker baru.
- Pengecualian Source COMPLIMENTARY aktif. Akun admin yang masih Gratis/trial tetap melihat promosi; kewenangan admin sendiri bukan pengecualian. Pelanggan Pro berbayar tetap melihat informasi paket setelah login, sesuai permintaan pengguna, dengan keterangan Pro sudah aktif.
- Popup dapat ditutup lewat Nanti saja atau Escape. Melihat atau menutup popup tidak membuat checkout, mandat autodebit atau tagihan.

Pengingat dalam aplikasi:
- H-7, H-3, H-1 dihitung dari timestamp kedaluwarsa aktual, dengan pembulatan hari ke atas. Banner berubah tingkat urgensinya; tidak memunculkan popup berulang setiap perpindahan menu.
- Untuk masa berbayar non-recurring, tampil tanggal berakhir dan tautan perpanjangan. Setelah kedaluwarsa, data dasar tetap tersedia.
- Jika recurring benar-benar berstatus ACTIVE, belum ada permintaan batal dan next_charge_at tersedia, tampil pengingat jadwal tagihan berikutnya dan tautan kelola perpanjangan.
- Tidak mengirim email/push, tidak mengubah tanggal trial/langganan, dan mengecualikan Pro gratis admin. Backend/status langganan diperiksa ulang saat fokus jendela dan setelah perubahan akses/penagihan; penghitung hari lokal diperbarui tiap menit tanpa query berkala.

Pengujian: scripts/test-pro-engagement.mjs (frontend) dan tests/test_pro_features.py (backend), ditambah regresi ekspor, rutin, Split Bill dan proxy. Tidak ada perubahan schema/database pada penambahan pengalaman Pro ini.

Verifikasi sesi: aturan popup/hari dan fallback storage lolos; regresi cache sesi lolos; proxy Pro mempertahankan cookie dan kode error lolos; 3 uji kemampuan Pro, 5 regresi rutin, 3 regresi ekspor dan 11 uji Split Bill lolos. Lint, TypeScript dan build produksi frontend lolos. Tidak ada pengujian visual browser atau pengiriman notifikasi eksternal pada sesi ini.

Pembaruan pembagian paket: permintaan pengguna mengeluarkan Transaksi dari Pro dan memasukkan Wishlist/Stok Kebutuhan. Ketentuan ini menggantikan pembagian awal pada catatan historis sebelumnya.
