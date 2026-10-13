# Ekspor Transaksi

Menu Transaksi menyediakan Ekspor PDF dan Ekspor Excel (.xlsx), menggantikan CSV. Ekspor mengikuti bulan, pencarian, jenis, rekening dan baris yang terlihat. Tanggal terbaru dahulu. Ekspor akun memerlukan login; tombol ekspor pada mode demo dinonaktifkan.

FE mengirim `Month`, `TransactionIds`, `Search`, `Kind`, `Bank` ke POST `/transactions/export/{pdf|xlsx}`. Backend membaca baris aktif milik pengguna saja, memeriksa bulan/filter dan ID unik (1–5000), lalu membangun laporan tanpa menulis database. Perubahan/void/baris yang tidak tersedia menghasilkan 409 dan pengguna diminta memuat ulang. Proxy memakai JWT HttpOnly, same-origin, no-store, nama file tetap tervalidasi dan tipe unduhan sesuai format. Tidak memicu refresh/mengulang penyimpanan transaksi.

PDF memakai A4 landscape, judul/periode/nama akun, ringkasan transaksi yang diekspor, tabel dengan rekening tersensor, catatan, dan nomor halaman. Header tabel diulang pada halaman berikutnya; catatan panjang dapat terpecah antar halaman.

Excel memakai satu sheet Transaksi, delapan kolom, angka/tanggal asli, nominal format rupiah, table/autofilter, freeze panes, dan rumus ringkasan. Rumus dihitung ulang saat dibuka/diedit di Excel; nilai cache awal disertakan untuk viewer. Deskripsi/catatan/rekening disimpan sebagai teks untuk menghindari formula injection. Mengedit file hasil ekspor tidak mengubah data aplikasi. Tidak ada fitur impor kembali pada perubahan ini.

Pendapatan mengecualikan Tarik Tunai dan Pengembalian Piutang. Pengembalian Piutang dihitung terpisah; Arus Kas Bersih = Pendapatan + Pengembalian Piutang - Pengeluaran. Transfer Antar Rekening dan Tarik Tunai disajikan terpisah. Ringkasan menggunakan **baris yang diekspor**, bukan semua transaksi bulan bila filter aktif.

Tidak membutuhkan migration atau paket baru: ReportLab dan openpyxl sudah ada pada backend. Deploy FE dan BE terbaru. Pemeriksaan memakai transaksi sintetis dan tidak mengubah database aplikasi.
