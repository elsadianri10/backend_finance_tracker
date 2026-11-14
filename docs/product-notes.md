# Catatan produk Finance Tracker

Tanggal awal: 16 Oktober 2026. Diperbarui: 3 November 2026.

Keputusan paket dan harga di bawah sudah diterapkan pada aplikasi. Pembayaran produksi belum aktif; identitas pengelola, kontak bantuan dan kebijakan publik masih disiapkan.

## Konsep monetisasi

Model awal yang diusulkan adalah paket Gratis dan satu paket Pro berlangganan, dengan pilihan pembayaran bulanan atau tahunan. Pengguna dapat membangun kebiasaan mencatat melalui fitur dasar, lalu berlangganan untuk pengelolaan yang lebih lengkap.

Nilai jual utama adalah pencatatan yang saling terhubung: pembayaran Tagihan tercatat di Transaksi, pembayaran cicilan mengurangi utang, dan setoran atau penarikan memperbarui Savings. Target awal yang diusulkan adalah karyawan yang saat ini mengelola beberapa rekening, tagihan rutin, dan cicilan menggunakan spreadsheet.

### Pembagian fitur terkini

| Fitur | Gratis | Pro |
| --- | --- | --- |
| Transaksi dan ringkasan dasar | Tersedia | Tersedia |
| Rekening dan tabungan | 3 rekening dan 3 simpanan aktif | Batas lebih besar |
| Pengeluaran Rutin | Maksimal 3 rencana aktif | Tanpa batas kecil tersebut |
| Hutang, Piutang, dan Tagihan | Data lama tetap tersimpan | Pengelolaan dan sinkronisasi pembayaran |
| Split Bill | Maksimal 2 grup aktif | Lebih banyak grup dan laporan lengkap |
| Laporan | Transaksi termasuk PDF dan Excel | PDF Split Bill dan laporan penunjang |
| Wishlist dan Stok Kebutuhan | Halaman harga; data lama tetap disimpan | Pengelolaan penuh |
| Keamanan, passkey, dan akses data lama | Tersedia | Tersedia |

Jumlah transaksi harian tidak dibatasi dalam usulan ini. Setelah langganan berakhir, data lama tetap dapat dibaca dan diekspor; fitur Pro kembali mengikuti batas paket Gratis. Data lama di atas batas tetap dapat dibaca dan diedit; penambahan slot aktif dan pemulihan arsip mengikuti batas paket.

### Harga yang disetujui 2 November 2026

- Pro bulanan: Rp29.000 per bulan.
- Pro tahunan: Rp249.000 per tahun.
- Tahunan menghemat Rp99.000 dibanding 12 pembayaran bulanan (Rp348.000), sekitar 28%. Ini perbandingan paket, bukan diskon sementara.
- Pengguna menginginkan perpanjangan otomatis/autodebit. Belum memiliki akun gateway. Rekomendasi teknis: Midtrans dengan integrasi Subscription API (GoPay/kartu kredit); Snap saja tidak mencukupi untuk autodebit. Integrasi Midtrans dilanjutkan atas persetujuan pengguna; pembuatan akun merchant dan aktivasi kanal recurring belum selesai.
- Autodebit hanya setelah persetujuan pengguna; trial tidak otomatis membuat mandat pembayaran. Integrasi wajib menyediakan pembatalan perpanjangan, tanggal tagihan berikutnya, serta penanganan pembayaran gagal.
- Integrasi checkout dan autodebit sudah dibuat, default nonaktif sampai akun/kunci dan aktivasi merchant Midtrans tersedia. Migration 028 telah diterapkan lokal tanpa perubahan record lama. Pembatasan PDF Split Bill serta slot aktif rekening/Savings/rutin/Split Bill sudah berlaku; belum ada pembayaran produksi. Lihat [langganan](subscriptions.md).

Untuk tahap awal, satu paket Pro diusulkan agar mudah dijelaskan dan dirawat. Paket akses selamanya belum disarankan karena biaya hosting dan pemeliharaan terus berjalan.

### Validasi sebelum peluncuran berbayar

Uji ke 20–30 calon pengguna dengan kebutuhan beberapa rekening, tagihan rutin, dan cicilan. Usulan awal adalah memberi uji coba Pro selama 30 hari, kemudian menilai penggunaan berulang, fitur yang paling membantu, kesediaan membayar, dan biaya melayani pengguna. Hasilnya menjadi dasar penyesuaian harga dan batas fitur.

Referensi pembanding dari pembahasan awal:

- [Spendee Premium](https://help.spendee.com/article/202-what-is-spendee-premium): paket dasar gratis dengan pilihan langganan berbayar.
- [Wallet Premium](https://support.budgetbakers.com/hc/en-us/articles/7151349344018-Everything-about-Premium): aplikasi dasar gratis dengan pilihan Premium.

Referensi ini menjadi contoh model paket, bukan dasar untuk menganggap harga usulan sudah sesuai pasar Indonesia.

Status terkini: pembatasan paket dan integrasi pembayaran sudah dibuat; merchant belum aktif. Kebijakan paket 3 November dan kesiapan rilis tercantum di [release-readiness.md](release-readiness.md).


## Perkembangan 2 November 2026

Dasar pengelolaan Paket & Akses sudah dibuat: status Gratis/Pro serta pemberian Pro gratis oleh admin dengan masa berlaku opsional dan riwayat. Checkout dan batas fitur tetap belum aktif. Lihat [pengaturan akses](account-access.md); migration 026 belum diterapkan ke database aplikasi pada sesi implementasi ini.

Trial Pro otomatis disetujui dan diimplementasikan selama 30 hari pada 2 November 2026. Migration 027 memulai trial akun lama pada waktu aktivasi; akun baru sejak login Google pertama. Tanggal dan sisa hari tampil di Profil/admin. Batas fitur dan penagihan otomatis tetap belum aktif.

Migration trial 027 telah diterapkan pada database lokal dengan backup dan validasi pelestarian data pada 2 November 2026. Database produksi terpisah tetap perlu migration sebelum backend baru.

Pengalaman Pro ditambahkan 2 November 2026: badge sidebar, halaman harga /pro, popup setelah login baru selain Pro gratis admin, dan pengingat dalam aplikasi H-7/H-3/H-1. Pemeriksaan server berlaku untuk PDF dan penambahan slot aktif di atas 3 rutin/2 Split Bill; data lama tetap dapat dikelola. Batas bank/Savings dan tier fitur lain belum ditetapkan/diaktifkan. Rincian: [pengalaman Pro](pro-experience.md).

Revisi paket: Transaksi beserta PDF/Excel tetap Gratis. Wishlist dan Stok Kebutuhan masuk Pro. Badge Pro hanya muncul pada Gratis yang trial-nya sudah habis; trial aktif, Pro berbayar dan Pro admin tidak melihat badge. Tautan Wishlist dan reservasi hadiah untuk penerima tetap tersedia tanpa Pro.


### Keputusan 3 November 2026

Gratis: 3 rekening dan 3 simpanan aktif. Arsip/pulihkan membebaskan slot tanpa menghapus saldo/riwayat. Tagihan dan Hutang/Piutang beserta sinkronisasi pembayaran memerlukan Pro. Kelola Wishlist/Stok Kebutuhan dan PDF Split Bill Pro; Transaksi/PDF/Excel transaksi Gratis. Identitas pengelola dan kontak bantuan belum dipilih: halaman kebijakan disiapkan sebagai draft lokal, belum diterbitkan di produksi. Lihat release-readiness.md untuk aturan terkini dan langkah sebelum rilis.


Pembaruan paket 3 November 2026: Tagihan dan Hutang/Piutang menjadi Pro, termasuk pembuatan, perubahan dan pembayaran melalui jalur Transaksi/Rutin. Pembacaan data lama serta operasi penghapusan yang sudah diizinkan tetap tersedia. Transaksi dan ekspor PDF/Excel transaksi tetap Gratis. Batas aktif rekening/Savings/rutin/Split Bill tidak berubah. Tidak memerlukan migrasi atau perubahan data keuangan.
