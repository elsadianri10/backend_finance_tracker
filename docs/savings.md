# Savings

Savings mencatat aset milik pengguna dalam tiga jenis: CASH (tabungan uang), GOLD (Logam Mulia: Emas/Perak), DEPOSIT (deposito). Saldo rekening bank tidak berubah otomatis. Tidak ada transaksi pembelian/penjualan emas, transfer bank, harga pasar otomatis, atau bunga deposito otomatis.

## Data dan riwayat

MetalType menerima GOLD atau SILVER hanya untuk Kind GOLD (identifier lama tetap dipertahankan untuk kompatibilitas API). Data emas lama dimigrasikan ke MetalType GOLD. Request lama yang tidak mengirim MetalType saat create GOLD dianggap emas; saat edit mempertahankan jenis logam lama. MetalType tidak dapat berubah setelah ada riwayat. Ringkasan gram dan estimasi emas/perak terpisah; nilai logam tanpa harga tidak ikut estimasi dan ringkasan ditandai sebagian jika ada harga yang belum diisi.


- CASH: nama, nominal awal rupiah, tanggal mulai, rekening dari My Bank Account atau tunai, notes.
- GOLD: jenis logam Emas/Perak, nama, tanggal beli, berat per keping (3 desimal gram), jumlah keping awal, total harga beli awal opsional, harga per gram saat ini opsional, notes. Jumlah awal = berat × keping. Jumlah saat ini mengikuti riwayat perubahan dalam gram; keping pada detail merupakan jumlah awal.
- DEPOSIT: nama, nominal pokok awal, rekening bank sendiri, tanggal mulai/jatuh tempo, bunga per tahun opsional, notes. Ringkasan hanya menghitung pokok, bukan bunga/pajak. Setelah rekening dihapus, snapshot bank dan nomor tersensor tetap tersedia.
- Ringkasan tabungan, pokok deposito, gram emas, dan gram perak dihitung terpisah. Estimasi logam = gram saat ini × harga per gram manual, dibulatkan ke rupiah terdekat; tanpa harga ditampilkan belum dicatat. Harga beli awal tetap terpisah dari estimasi saat ini.
- Tambah/kurangi memakai Amount berupa rupiah bulat untuk uang/deposito, atau desimal gram maksimal 3 angka untuk emas/perak. Pengurangan tidak boleh melebihi simpanan. Tanggal harus berurutan, tidak sebelum tanggal awal, dan tidak melebihi hari ini UTC+7.
- Setelah ada riwayat, jenis, jumlah awal, berat/keping awal dan tanggal awal terkunci. Nama, rekening, notes, harga emas serta informasi deposito dapat diedit. Gunakan riwayat untuk perubahan jumlah. Riwayat yang sudah tersimpan tidak diedit/dihapus satu per satu.
- Hapus simpanan menghapus riwayatnya setelah konfirmasi; rekening bank tidak dihapus. Data Savings tidak mempunyai batas tampilan riwayat 3 bulan.
- Batas saldo uang Rp 1 triliun; emas 1 juta gram; harga per gram maksimal Rp 1 miliar. Numerik disimpan sebagai NUMERIC dan dihitung menggunakan Decimal.

## API

Semua endpoint menggunakan JWT aplikasi dan ownership user aktif. Respons no-store. FE Next.js membaca JWT dari cookie HttpOnly di server; mutasi memeriksa same-origin. Respons hanya menyertakan metadata bank tersensor, tanpa token, nomor rekening/kartu penuh, atau ciphertext.

| Method | Path | Kegunaan |
| --- | --- | --- |
| GET/POST | `/savings` | Daftar/buat simpanan |
| GET/PATCH/DELETE | `/savings/{id}` | Detail/edit/hapus |
| POST | `/savings/{id}/movements` | Tambah/kurangi |

Create GOLD: `{ "Kind":"GOLD", "Name":"Antam", "StartDate":"2026-10-08", "WeightPerPiece":"5", "Pieces":2, "PurchaseCost":15000000, "PricePerGram":1700000 }`.

Create CASH: `{ "Kind":"CASH", "Name":"Dana Darurat", "StartDate":"2026-10-08", "OpeningAmount":1000000, "BankAccountId":null }`.

DEPOSIT menggunakan OpeningAmount, BankAccountId, MaturityDate dan InterestRate opsional. Saat edit, BankAccountId yang tidak dikirim mempertahankan sumber lama; null menghapus sumber pada CASH. Field tersembunyi milik jenis lain harus dihilangkan/null.

Movement: `{ "RequestId":"<uuid>", "Direction":"ADD", "Amount":"0.5", "MovementDate":"2026-10-08", "Notes":"Tambah emas" }`. RequestId idempotent; request ulang dengan ID yang sama tetapi isi berbeda mendapat 409. Mutasi menggunakan row lock simpanan untuk mencegah pengurangan bersamaan melewati saldo.

401 sesi invalid, 403 user nonaktif, 404 bukan milik pengguna/tidak ditemukan, 409 konflik atau jumlah awal terkunci, 422 validasi field. Error form menggunakan detail[].loc.

## Database dan verifikasi

Database lama memakai `010_savings.sql` lalu `011_savings_precious_metals.sql` dan `012_savings_price_date.sql`; database baru memakai `000_init.sql`, yang sudah mencakup sampai 012. Reset default juga mengosongkan savings/saving_movements dan tetap mempertahankan wallet_providers. Upgrade tidak memakai reset.

Tes: `python -m unittest discover -s tests -p test_savings.py`, `python tests/check_database_baseline.py`, serta FE `npm run build` dan `npm run test:savings`. Pengujian UI menggunakan data sintetis; screenshot disimpan di FE `preview/`.

PriceDate (YYYY-MM-DD) otomatis memakai hari ini UTC+7 saat harga per gram pertama kali diisi atau nilainya berubah. Edit nama, notes, biaya beli, atau jumlah tidak memperbarui tanggal harga. Mengosongkan harga mengosongkan tanggalnya; harga lama tanpa tanggal tetap NULL sampai harga berubah. Detail/ringkasan menampilkan DD-MM-YYYY; ringkasan dengan beberapa tanggal memakai rentang tanggal harga dan menandai tanggal yang belum diketahui.
