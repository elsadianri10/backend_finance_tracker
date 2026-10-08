# My Bank Account

Migration `008_wallet_providers_bank_accounts.sql` mengganti nama `billing_platforms` menjadi `wallet_providers`. ID, nama, status aktif, foreign key akun tagihan, dan seluruh data tagihan tetap dipertahankan. Kolom `bank_f` menerima integer 0/1, default 0. Seed BCA/BRI bernilai 1. Bank custom perlu ditandai secara eksplisit:

```sql
INSERT INTO wallet_providers (id, name, bank_f) VALUES (8, 'Bank Baru', 1);
-- Provider nonbank tetap dapat ditambahkan dengan bank_f = 0.
```

Database lokal telah menerima migration 008 pada 7 Oktober 2026. Database deployment yang sudah sampai 007 perlu menjalankan 008 sekali. Database baru cukup menjalankan baseline 000, yang sudah mencakup 008. Default reset 000 juga mengosongkan `bank_accounts` sambil mempertahankan seluruh provider dan BankF.

## Endpoint

Semua endpoint memerlukan JWT aplikasi, menegakkan pengguna aktif/kepemilikan, dan merespons `Cache-Control: no-store`.

| Method | Path | Hasil |
| --- | --- | --- |
| GET | `/bank-accounts/platforms` | Provider aktif dengan BankF=1, abjad |
| GET | `/bank-accounts` | Daftar rekening milik pengguna, abjad platform |
| POST | `/bank-accounts` | Create, 201 |
| GET | `/bank-accounts/{id}` | Detail, akun pengguna lain 404 |
| PATCH | `/bank-accounts/{id}` | Edit, 200 |
| DELETE | `/bank-accounts/{id}` | Hapus catatan rekening, 204 |

Payload create menggunakan PascalCase: `PlatformId`, `AccountNumber` (string 5–30 digit), `CardNumber` (string 12–19 digit), `ValidThru` (`YYYY-MM`), `AdminFee` dan `OthersFee` (rupiah bulat 0–1 triliun, default 0). Ketiga field nomor/tanggal kartu wajib saat create. Kedaluwarsa diperbolehkan untuk arsip. Biaya bersifat bulanan dan hanya dicatat; tidak otomatis mengurangi saldo/membuat transaksi.

Saat PATCH, kirim seluruh metadata. Hilangkan `AccountNumber`/`CardNumber` untuk mempertahankan nomor lama; null atau string kosong ditolak. Provider yang sekarang tidak aktif/bukan bank masih dapat dipertahankan oleh akun lama; create/pindah platform harus menuju bank aktif.

Respons hanya berisi `Id`, `PlatformId`, `PlatformName`, `AccountNumberMasked`, `CardNumberMasked`, `ValidThru`, `AdminFee`, `OthersFee`. Nomor rekening dan kartu dienkripsi AES-256-GCM dengan nonce acak serta AAD terikat ke pengguna, akun, dan jenis field agar ciphertext tidak bisa ditukar. Memakai konfigurasi ENCRYPTION_KEY yang sama; tidak ada nomor asli/ciphertext/kunci/token pada respons. Error input tidak menggemakan nomor. Encryption config yang tidak tersedia menghasilkan 503.

Frontend `/bank-accounts` memakai proxy Next `/api/bank-accounts` dengan cookie sesi HttpOnly, same-origin pada POST/PATCH/DELETE, no-store, dan proyeksi respons masked-only. Nomor lengkap hanya berada dalam form lokal dan dibersihkan saat tutup/berhasil; tidak disimpan dalam localStorage/state global. Hapus memakai konfirmasi dan menghapus catatan saja; tidak menutup rekening bank sebenarnya. Akun debit dan akun Tagihan terpisah, sehingga edit/hapus salah satunya tidak mengubah yang lain.

Tagihan tetap menggunakan API `/billing/platforms` untuk kompatibilitas, kini disertai `BankF`. Semua provider aktif (BankF 1 maupun 0) tersedia; urutan bank abjad dahulu, lalu nonbank abjad. `PlatformType` tetap hanya di akun Tagihan. Label input `AccountNumber` berubah menjadi **Card Number**, tetapi key API dan ciphertext Tagihan lama tetap dipertahankan.

## Validasi

`tests/test_bank_accounts.py`: filter/urutan provider, create/edit/delete, otorisasi owner, validasi field, masking, AAD, menjaga nomor pada edit, dan kegagalan enkripsi tanpa penyimpanan parsial.

`tests/check_wallet_migration.py`: migration 001–008 dalam schema sintetis, provider custom/foreign key/ID tetap utuh. `--apply` mengupgrade schema aplikasi dari 007 tanpa reset dan membandingkan jumlah data/provider.

`tests/check_database_baseline.py`: baseline terbaru dengan init non-destruktif dan reset hanya di schema sintetis.

Frontend `node scripts/test-bank-accounts.mjs`: server backend palsu dan Next lokal; JWT server-side, same-origin, filter bank, urutan, CRUD, no-store, proyeksi/penyensoran error. Tambahkan `--preview` untuk UI data sintetis pada port 3124.
