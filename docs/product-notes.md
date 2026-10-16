# Catatan produk Finance Tracker

Tanggal catatan: 16 Oktober 2026.

Konsep monetisasi disimpan untuk dibahas kembali. Pembagian paket, harga, dan batas fitur di bawah merupakan usulan awal, belum keputusan implementasi atau penawaran kepada pengguna.

## Konsep monetisasi

Model awal yang diusulkan adalah paket Gratis dan satu paket Pro berlangganan, dengan pilihan pembayaran bulanan atau tahunan. Pengguna dapat membangun kebiasaan mencatat melalui fitur dasar, lalu berlangganan untuk pengelolaan yang lebih lengkap.

Nilai jual utama adalah pencatatan yang saling terhubung: pembayaran Tagihan tercatat di Transaksi, pembayaran cicilan mengurangi utang, dan setoran atau penarikan memperbarui Savings. Target awal yang diusulkan adalah karyawan yang saat ini mengelola beberapa rekening, tagihan rutin, dan cicilan menggunakan spreadsheet.

### Usulan pembagian fitur

| Fitur | Gratis | Pro |
| --- | --- | --- |
| Transaksi dan ringkasan dasar | Tersedia | Tersedia |
| Rekening dan tabungan | Jumlah terbatas, batas belum ditentukan | Batas lebih besar |
| Pengeluaran Rutin | Maksimal 3 rencana aktif | Tanpa batas kecil tersebut |
| Hutang, Piutang, dan Tagihan | Pencatatan dasar | Sinkronisasi pembayaran lengkap |
| Split Bill | Maksimal 2 grup aktif | Lebih banyak grup dan laporan lengkap |
| Laporan | Ekspor data dasar | PDF rapi, laporan lintas bulan, dan filter lengkap |
| Keamanan, passkey, dan akses data lama | Tersedia | Tersedia |

Jumlah transaksi harian tidak dibatasi dalam usulan ini. Setelah langganan berakhir, data lama tetap dapat dibaca dan diekspor; fitur Pro kembali mengikuti batas paket Gratis. Perilaku atas data yang sudah melebihi batas perlu dirancang sebelum implementasi, dengan tetap mempertahankan data pengguna.

### Hipotesis harga

- Pro bulanan: Rp19.000 per bulan.
- Pro tahunan: Rp190.000 per tahun.
- Opsi promosi pengguna awal: Rp149.000 untuk tahun pertama, dengan harga perpanjangan dijelaskan sejak pembelian.

Harga tersebut perlu diuji terhadap kesediaan bayar pengguna. Sebagai ilustrasi, 100 pelanggan bulanan pada Rp19.000 menghasilkan pendapatan kotor Rp1.900.000 per bulan, sebelum biaya infrastruktur, pemrosesan pembayaran, pajak, dan dukungan. Angka ini bukan perkiraan laba atau target penjualan yang sudah tervalidasi.

Untuk tahap awal, satu paket Pro diusulkan agar mudah dijelaskan dan dirawat. Paket akses selamanya belum disarankan karena biaya hosting dan pemeliharaan terus berjalan.

### Validasi sebelum peluncuran berbayar

Uji ke 20–30 calon pengguna dengan kebutuhan beberapa rekening, tagihan rutin, dan cicilan. Usulan awal adalah memberi uji coba Pro selama 30 hari, kemudian menilai penggunaan berulang, fitur yang paling membantu, kesediaan membayar, dan biaya melayani pengguna. Hasilnya menjadi dasar penyesuaian harga dan batas fitur.

Referensi pembanding dari pembahasan awal:

- [Spendee Premium](https://help.spendee.com/article/202-what-is-spendee-premium): paket dasar gratis dengan pilihan langganan berbayar.
- [Wallet Premium](https://support.budgetbakers.com/hc/en-us/articles/7151349344018-Everything-about-Premium): aplikasi dasar gratis dengan pilihan Premium.

Referensi ini menjadi contoh model paket, bukan dasar untuk menganggap harga usulan sudah sesuai pasar Indonesia.

Belum ada pembatasan akun, penagihan langganan, atau migrasi database dari catatan monetisasi ini.
