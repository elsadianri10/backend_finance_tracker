# Stok Kebutuhan

Kategori utama: Kesehatan (vitamin/suplemen, obat), Konsumsi (makanan/minuman), Beauty & Body Care (skincare, oral care, body care, hair care, makeup). Subkategori dibatasi sesuai kategori dan divalidasi server.

Satu kebutuhan, misalnya Sunscreen, memiliki beberapa produk/brand/varian. Setiap produk menyimpan label satuan/isi kemasan, pilihan Andalan/Sedang Dicoba, jumlah kemasan sedang dipakai dan cadangan, penanda Hampir Habis serta tanggal membuka kemasan terakhir yang opsional. Tidak ada hitung tablet/porsi, pengurangan harian otomatis, atau prediksi tanggal habis. Tambah produk untuk mencoba brand baru; snapshot brand/varian dalam riwayat tetap mengikuti saat pencatatan.

## Pemakaian dan beli ulang

- Buka 1 Cadangan: cadangan berkurang satu dan dipakai bertambah satu.
- 1 Kemasan Habis: dipakai berkurang satu. Checkbox opsional membuka satu cadangan jika tersedia. Form tanggal kejadian default hari ini, WIB (UTC+7). Stok tidak boleh negatif.
- Hampir Habis: penanda manual. Saat tidak ada cadangan dalam kebutuhan tersebut, masuk daftar beli ulang; membatalkan penanda menghapus alasan tersebut. Cadangan dari brand lain dalam kebutuhan yang sama tetap dihitung.
- Bulanan: next_review hanya pengingat cek kebutuhan, bukan tanggal pasti habis. Pembelian pada/setelah tanggal pengingat memajukannya satu bulan kalender dari tanggal pembelian. Pembelian lebih awal tidak menggeser pengingat yang masih di depan.
- Saat stok menipis: total cadangan produk aktif kurang dari atau sama dengan batas memunculkan pengingat. Stok kosong tanpa produk belum memunculkan pengingat.
- Manual: tidak masuk daftar secara otomatis; gunakan Masukkan ke Belanja Ulang atau tandai Hampir Habis.
- Lewati Bulan Ini untuk pola bulanan menunda pengingat bulan berjalan; tidak menambah stok. Jeda Beli Ulang menyembunyikan semua pengingat sampai Aktifkan Lagi. Masukkan ke Belanja Ulang adalah tindakan eksplisit yang mengaktifkan kembali pengingat dan membatalkan penundaan.
- Arsip kebutuhan menyembunyikannya dari daftar aktif/beli ulang, tanpa menghapus stok dan riwayat. Produk hanya bisa diarsipkan setelah stok kosong. Pulihkan melalui tab Diarsipkan atau Edit Produk.

Pengingat tersedia **di dalam menu aplikasi**, bukan email/push/WhatsApp. Data diperiksa lagi ketika halaman dibuka ulang dan saat pergantian hari jika tab masih terbuka. GET/penggunaan filter tidak menulis database. Setiap perubahan sukses memperbarui data tampilan yang terdampak.

## Pembelian dan transaksi

Catat Pembelian menambah jumlah ke cadangan. Buka kemasan dilakukan terpisah. Harga opsional adalah total pembelian; toko dan catatan disimpan dalam riwayat. Checkbox Sekalian Catat sebagai Pengeluaran **default tidak dicentang**. Saat dicentang, harga harus positif; rekening opsional berarti tunai/tidak dicatat, dan rekening milik orang lain ditolak. Kategori Transaksi: Kesehatan → health, Konsumsi → food, Beauty & Body Care → shopping.

Pembelian, stok dan ledger disimpan dalam satu transaksi database. Lock pemilik mengikuti urutan layanan keuangan; versi data mencegah dua tab menggandakan pembelian dan RequestId + hash memastikan retry identik tidak membuat stok/pengeluaran kedua. RequestId berbeda dengan versi lama atau pemakaian ulang RequestId dengan isi berbeda ditolak 409. Setelah konflik, muat ulang untuk menggunakan versi terbaru.

Riwayat menampilkan 100 kejadian terbaru per kebutuhan, termasuk penyesuaian stok. Perubahan stok awal melalui Edit Produk dicatat sebagai penyesuaian dan tidak membuat pengeluaran. Riwayat pembelian adalah catatan saat pembelian: mengedit/membatalkan Transaksi tidak mengubah stok atau nominal historis; pembatalan pengeluaran diberi label pada riwayat. Jangan catat pengeluaran lagi melalui menu Transaksi jika checkbox pembelian sudah digunakan. Stok tidak terhubung otomatis ke Wishlist atau Pengeluaran Rutin.

## API dan database

Route decorator FastAPI → controller → service. `/stock-needs`: GET/POST; `/{id}`: PATCH; `/{id}/actions`: POST; `/{id}/products`: POST; `/{id}/products/{productId}`: PATCH; `/{id}/products/{productId}/actions` dan `/purchases`: POST; `/{id}/history`: GET. Semua memerlukan sesi login/passkey dan pemeriksaan kepemilikan ID induk/anak. Tidak tersedia link berbagi publik untuk stok. Proxy frontend menerapkan pemeriksaan origin, sesi, whitelist route dan respons no-store.

Tiga tabel relasional bertipe: stock_needs, stock_products, stock_events. Tidak ada JSON/JSONB untuk data aplikasi. Tidak ada penghapusan permanen melalui UI; arsip menjaga riwayat.

## Deployment dan verifikasi

Database yang sudah melalui migration 023: jalankan **hanya database/024_stock_needs.sql**, lalu deploy backend dan frontend. Migration additive dan dapat diulang; tidak mengubah tabel/data keuangan atau Wishlist. Jangan jalankan 000 untuk upgrade database berisi data. Database baru boleh memakai baseline 000 yang sudah mencakup 024. Tidak ada env/dependency baru.

Verifikasi migrasi dilakukan hanya di schema sintetis acak yang dibuang, termasuk snapshot semua data sebelum/sesudah upgrade, upgrade berulang pada stok terisi, dua pembelian PostgreSQL bersamaan, retry identik, dan baseline/reset. Database aplikasi tidak direset atau di-upgrade oleh pemeriksaan ini.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_stock_needs.py
.\.venv\Scripts\python.exe tests/check_stock_migration.py
.\.venv\Scripts\python.exe tests/check_database_baseline.py
```

Frontend: npm run test:stock-needs, npx tsc --noEmit, lint file terkait, npm run build. Pratinjau memakai npm run test:stock-needs -- --preview dengan akun/data tiruan.
