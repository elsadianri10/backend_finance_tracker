# Wishlist

Menu Wishlist menyimpan daftar pribadi dengan jenis Things, Consumeables, Games, Foods & Drinks, Holiday, Dream Transportation, dan Dream Gadget. Pengguna dapat membuat beberapa daftar dan grup bernama sendiri, termasuk grup aksesori atau Utama/Pribadi dan Rumah Jepara. Grup dapat diubah namanya atau dihapus beserta barangnya.

Barang menyimpan nama, toko/platform, merek, catatan/variasi, link, perkiraan harga opsional, prioritas, dan status. Holiday memiliki negara/provinsi/kota; kendaraan memiliki model/tahun/warna/plat impian; gadget memiliki model/kapasitas/warna. Foto memakai maksimal enam URL HTTP/HTTPS per barang, satu URL per baris; versi ini belum mengunggah file gambar. Data screenshot tidak otomatis diimpor.

Status tersedia: diinginkan, sold out, terpenuhi/dibeli, dan diarsipkan. Barang sold out/terpenuhi/arsip tidak dapat direservasi. Mengubah status dari diinginkan menghapus reservasi aktif; arsip hanya terlihat oleh pemilik. Subtotal grup dan total daftar menjumlahkan harga yang diketahui untuk barang yang belum terpenuhi/diarsipkan; reservasi belum berarti pembelian dan tidak mengurangi total.

## Berbagi dan reservasi

- Semua daftar pribadi sampai pemilik menekan Bagikan. Token acak 256 bit disimpan sebagai hash SHA-256; token asli hanya dikembalikan saat membuat link. Membuat link baru mencabut link sebelumnya; Cabut Link menghentikan akses selanjutnya tanpa menghapus reservasi.
- Link membuka `/wishlist/shared/{token}` tanpa sidebar atau data keuangan. Respons tidak disimpan cache, tidak diindeks dan tidak mengirim referrer melalui foto/link produk.
- Things, Consumeables, Games dan Foods & Drinks membolehkan reservasi setelah login Google + passkey. Holiday dan Dream hanya bisa dibaca. Penerima yang mencoba mencentang tanpa sesi diarahkan ke login, lalu kembali melalui tujuan lokal yang divalidasi ketat.
- Check adalah reservasi, bukan konfirmasi pembayaran. Orang lain hanya dapat membatalkan reservasi sendiri. Pemilik dapat membatalkan semua reservasi dan menandai barang sendiri. Nama pemesan hanya terlihat oleh pemilik dan pemesan tersebut; pengunjung lain hanya melihat status sudah direservasi.
- Setiap barang dapat dipilih terpisah meskipun berada dalam satu grup. Primary key reservasi per barang dan lock PostgreSQL pada daftar/barang memastikan hanya satu pemesan yang menang saat request bersamaan. Operasi cabut link, edit, hapus dan reservasi menggunakan lock daftar yang sama.
- Wishlist tidak membuat Transaksi, mengubah Savings, atau melakukan pembelian.

## API dan penyimpanan

Route decorator FastAPI diteruskan ke controller, lalu service. Endpoint `/wishlists` untuk daftar milik pengguna, `/{id}/groups`, `/{id}/items`, `/{id}/share`, dan `/{id}/items/{itemId}/reservation` mengelola data pemilik. `/wishlists/shared/{token}` menyediakan tampilan publik, dengan endpoint reservasi publik yang tetap membutuhkan autentikasi. Semua ID anak diperiksa terhadap daftar milik pemilik atau daftar pada link tersebut.

Lima tabel relasional baru: `wishlists`, `wishlist_groups`, `wishlist_items`, `wishlist_photos`, dan `wishlist_reservations`. Semua kolom bertipe; tidak ada JSON/JSONB untuk data aplikasi. Foreign key menghapus anak saat daftar/grup/barang dihapus.

## Deployment dan verifikasi

1. Untuk database yang sudah ada, jalankan **hanya** `database/022_wishlists.sql` setelah migration 021. Migration 022 hanya membuat tabel/index baru, tanpa mengubah data keuangan. Jangan menjalankan baseline 000 pada database berisi data untuk upgrade.
2. Deploy backend dan frontend terbaru. Konfigurasi passkey yang sudah digunakan tetap berlaku.
3. Database baru dapat memakai baseline 000 yang sudah mencakup 022. Mode reset 000 menghapus Wishlist juga, sehingga pemeriksaannya hanya dilakukan dalam schema sintetis.

Perintah pengujian:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_wishlists.py
.\.venv\Scripts\python.exe tests/check_wishlist_migration.py
.\.venv\Scripts\python.exe tests/check_database_baseline.py
```

Frontend: `npm run test:wishlists`, `npm run test:passkeys`, `npm run test:passkey-browser`, dan `npm run test:session`. Pengujian UI menggunakan server backend tiruan dan data sintetis; tidak mendaftarkan passkey atau membagikan Wishlist nyata. PostgreSQL diuji pada schema acak yang dibuang setelah selesai, termasuk pelestarian semua record sebelum/sesudah upgrade dan dua reservasi bersamaan. Tidak ada migration/reset yang dijalankan pada schema aplikasi dari pemeriksaan ini.
