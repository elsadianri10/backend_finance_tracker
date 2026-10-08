# Tagihan: Add Account

Tahap ini hanya setup akun bank/paylater. Detail transaksi, cicilan, kalkulasi periode, edit, dan hapus akun belum dibuat.

## API backend

Semua endpoint memerlukan JWT aplikasi pada `Authorization: Bearer <token>`:

| Method | Path | Kegunaan |
| --- | --- | --- |
| GET | `/billing/platforms` | Pilihan platform dari DB beserta tipe yang didukung |
| POST | `/billing/accounts` | Simpan akun milik user login, respons 201 |
| GET | `/billing/accounts` | Daftar akun milik user login |
| GET | `/billing/accounts/{id}` | Detail akun milik user login; akun user lain mendapat 404 |

FE Next.js yang sudah ada memakai cookie sesi HttpOnly. Tambahkan route proxy server Next.js untuk endpoint di atas; baca cookie di server lalu teruskan JWT ke backend. Jangan kirim JWT, nomor kartu lengkap, atau kunci enkripsi dari server ke komponen browser setelah penyimpanan. POST proxy harus mengikuti pemeriksaan same-origin yang sudah dipakai login. Respons dan fetch akun gunakan `no-store`.

Platform API mengembalikan array:

```json
[{"Id": 1, "Name": "BCA", "SupportedTypes": ["CREDIT_CARD"]}]
```

Setelah migrasi `004_account_only_platform_type.sql`, `billing_platforms` hanya menyimpan identitas platform (`id`, `name`) dan status aktif. Tambahkan platform lewat INSERT nama dan ID; tidak perlu kolom atau tabel tipe di master platform. `platform_type` hanya tersimpan pada `billing_accounts`, wajib dan hanya menerima `CREDIT_CARD` / `PAY_LATER`. Semua platform aktif menyediakan kedua pilihan tipe. API mempertahankan `SupportedTypes` berisi keduanya agar FE kompatibel. FE tetap memuat daftar platform dari API; label tipe “Credit Card” / “Pay Later”.

## Form Add Account

| Field | Kontrol | Aturan |
| --- | --- | --- |
| Platform | Dropdown | Wajib, nilai `PlatformId` dari API |
| Platform Type | Dropdown | Wajib, tipe yang didukung platform |
| Account Type | Text | Hanya Credit Card; wajib, misalnya BCA Batman atau BRI - Tokopedia Card |
| Account Number | Text dengan `inputMode="numeric"` | Hanya Credit Card; wajib, 12–19 digit, kirim string |
| Valid Thru | Month picker | Hanya Credit Card; wajib, kirim `YYYY-MM`, misalnya `2029-07` |
| Has a fixed bill date? | Checkbox/switch | Boolean wajib; berlaku untuk kedua tipe |
| Billing Date | Number/select 1–31 | Tampil dan wajib jika fixed = true |
| Due Date | Number/select 1–31 | Tampil dan wajib jika fixed = true |

Interpretasi poin e/f: checkbox mengontrol Billing Date dan Due Date. Account Type, Account Number, dan Valid Thru dikontrol Platform Type, sehingga ketiganya tetap tampil untuk kartu tanpa fixed bill date.

Account Number merupakan identitas digit, bukan nilai hitung. `type="number"` bisa menghilangkan nol di depan atau membulatkan nomor panjang; gunakan text + numeric keyboard. Boleh menerima spasi visual saat input, tetapi hilangkan spasi sebelum submit. Jangan simpan nomor lengkap dalam localStorage, URL, log, analytics, atau state global. Kosongkan input ketika form ditutup atau berhasil disimpan.

Saat berubah ke Pay Later, hapus ketiga field kartu dari payload atau set null. Saat fixed dimatikan, hapus BillingDate dan DueDate atau set null. Backend menolak field tersembunyi yang masih berisi nilai dengan 422. Valid Thru menyimpan bulan/tahun; tanggal harian tidak dikirim. Kartu kedaluwarsa tetap boleh dicatat untuk arsip akun; transaksi belum dibatasi pada tahap ini.

BillingDate dan DueDate adalah hari dalam bulan, bukan tanggal penuh. Aturan kalkulasi periode akan dibuat bersama detail transaksi. Jika tanggal 29–31 tidak ada pada bulan tertentu, rencana perhitungan menggunakan hari terakhir bulan itu. Hubungan bulan terbit dan jatuh tempo belum dihitung pada tahap Add Account.

## Contoh request

Credit Card:

```json
{
  "PlatformId": 1,
  "PlatformType": "CREDIT_CARD",
  "AccountType": "BCA Batman",
  "AccountNumber": "0123456789012345",
  "ValidThru": "2029-07",
  "HasFixedBillDate": true,
  "BillingDate": 20,
  "DueDate": 5
}
```

Pay Later tanpa fixed date:

```json
{
  "PlatformId": 3,
  "PlatformType": "PAY_LATER",
  "HasFixedBillDate": false
}
```

Respons create/detail dan elemen list:

```json
{
  "Id": "<uuid>",
  "PlatformId": 1,
  "PlatformName": "BCA",
  "PlatformType": "CREDIT_CARD",
  "AccountType": "BCA Batman",
  "AccountNumberMasked": "************2345",
  "ValidThru": "2029-07",
  "HasFixedBillDate": true,
  "BillingDate": 20,
  "DueDate": 5
}
```

Untuk Pay Later, AccountType, AccountNumberMasked, dan ValidThru bernilai null. Tanggal bernilai null jika fixed = false. FE cukup menampilkan `AccountNumberMasked`; backend mendekripsi lalu menyensor nomor, tanpa mengembalikan nomor asli atau ciphertext. Enkripsi memakai AES-256-GCM dengan nonce acak dan mengikat ciphertext ke akun serta pemiliknya.

## Tampilan dan error

Di menu Tagihan tampilkan tombol **Add Account**, daftar akun, state kosong, loading, dan error. Kartu daftar bisa menampilkan PlatformName, AccountType, AccountNumberMasked, ValidThru, dan ringkasan fixed date. Nonaktifkan tombol simpan saat request berjalan untuk menghindari submit ganda.

- 401: sesi tidak valid; arahkan login.
- 403: user nonaktif.
- 404: akun tidak ditemukan atau bukan milik user.
- 422: field tidak valid, tipe akun tidak valid, atau platform tidak tersedia; tampilkan error form berdasarkan `detail[].loc` untuk validasi field. Error platform memakai string `detail`.
- 503: konfigurasi enkripsi belum tersedia atau tidak dapat membaca nomor; tampilkan error layanan tanpa meminta user mengisi ulang secret.

Belum ada deteksi akun duplikat: dua kartu pada platform yang sama diperbolehkan dan `AccountType` membantu membedakannya.

## Setup backend

Untuk database baru, jalankan `database/000_init.sql` saja; baseline sudah mencakup migration 001–006. Database lama memakai migration yang belum diterapkan. Aplikasi tidak melakukan auto-migration.

Isi `ENCRYPTION_KEY` backend dengan hasil `python -c "import secrets; print(secrets.token_hex(32))"` jika belum tersedia, lalu restart backend. Jangan ganti key setelah akun tersimpan tanpa migrasi enkripsi; key lama dibutuhkan untuk membaca nomor yang sudah ada. Key ini tidak dikirim ke FE dan berbeda dari JWT SECRET_KEY.
