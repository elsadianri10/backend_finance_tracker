# Transaksi dan cicilan tagihan

Database baru cukup menjalankan `database/000_init.sql`, yang sudah mencakup fitur sampai migration 006. Untuk database lama, jalankan hanya migration yang belum diterapkan. Migration 002 telah diterapkan pada database lokal dalam sesi pengembangan 7 Oktober 2026; untuk database lain jalankan sekali. Tidak ada auto-migration saat startup.

Semua endpoint memerlukan JWT aplikasi dan memastikan pemilik akun. Data pengguna lain menghasilkan 404.

| Method | Endpoint | Fungsi |
| --- | --- | --- |
| GET / POST | `/billing/accounts/{account_id}/transactions` | Daftar / tambah transaksi |
| GET | `/billing/transactions/{transaction_id}` | Rincian dan jadwal cicilan |
| PATCH | `/billing/transactions/{transaction_id}/last-amount` | `{ "Amount": 1499500 }` untuk tagihan terakhir yang belum lunas |
| POST | `/billing/transactions/{transaction_id}/installments/{installment_id}/pay` | Tandai tagihan berikutnya lunas |
| PATCH | `/billing/accounts/{account_id}` | Edit akun; payload lengkap seperti create, nomor kartu opsional untuk mempertahankan nomor lama |
| DELETE | `/billing/accounts/{account_id}` | Hapus akun dan riwayatnya hanya jika semua tagihan lunas atau tidak ada transaksi; respons 204 |

Respons akun sekarang menyertakan `HasTransactions` dan `CanDelete`. Mengganti platform/tipe setelah akun memiliki transaksi ditolak 409. Perubahan BillingDate/DueDate berlaku untuk transaksi berikutnya dan tidak mengubah jadwal yang sudah dibuat. Nomor kosong pada form edit dihapus dari payload sehingga ciphertext lama dipertahankan; mengganti nomor tetap memakai enkripsi server dan respons tersensor. Jika platform/tipe diganti ke kartu lain, nomor baru wajib diisi. Delete memeriksa kepemilikan, mengunci akun lalu transaksi, memeriksa semua tagihan, dan menghapus anak terlebih dahulu dalam satu transaksi database. Create transaksi memakai lock akun yang sama untuk mencegah race dengan delete/edit. Tagihan belum lunas menghasilkan 409; data pengguna lain 404. FE memeriksa same-origin untuk PATCH/DELETE dan meneruskan respons 204 tanpa JSON; semua respons tetap no-store.

Request create menggunakan `Description`, `Tenor` (0, 3, 6, 9, 12, 18, 24), `FirstInstallment` / `LastInstallment` (YYYY-MM-DD), `Amount` (bilangan bulat rupiah per cicilan), dan `Notes` opsional. Nominal memakai NUMERIC(18,0), bukan float; input dibatasi ke integer aman JavaScript.

Bulan pertama adalah bulan jatuh tempo, bukan bulan transaksi atau bulan penerbitan tagihan. Jumlah jadwal = tenor, atau satu untuk tenor 0. Tenor 0 menghasilkan satu tagihan; form memberi default bulan depan, tetapi tanggal pertama boleh dipilih manual. Bulan terakhir wajib cocok dengan jumlah tenor. Hari jatuh tempo mengikuti DueDate akun fixed, atau hari pada FirstInstallment untuk akun nonfixed. Tanggal 29–31 dijepit ke akhir bulan tanpa menggeser anchor bulan berikutnya. FirstInstallment mempertahankan tanggal pilihan pengguna; LastInstallment dihitung otomatis dari tanggal tersebut dan tenor. DueDate pada setiap jadwal mengikuti aturan akun secara terpisah. Aturan ini tetap berlaku untuk Sekali Bayar dan Cicilan. Langganan memakai tanggal penagihan dan aturan periode tersendiri di bawah.

Respons memiliki field publik transaksi serta `Installments` berisi `Id`, `Sequence`, `Amount`, `DueDate`, `PaidAt`. Tidak ada JWT, nomor kartu asli, atau ciphertext. Tidak ada endpoint membatalkan pembayaran. API mutasi mengunci row transaksi PostgreSQL sebelum memeriksa urutan; pembayaran melompat, pembayaran ulang, atau perubahan tagihan terakhir setelah lunas menghasilkan 409. Pemilik boleh mencatat lunas sebelum tanggal jatuh tempo. UI meminta konfirmasi permanen sebelum mencatat lunas; aksi ini hanya pencatatan, tidak memindahkan uang.

Pengujian: `.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_billing*.py'`. Fixtures memakai SQLite sementara dan tidak menyentuh data akun asli. `.venv/Scripts/python.exe tests/check_billing_postgres.py` menguji row lock dan request pembayaran bersamaan dalam schema PostgreSQL acak yang dibersihkan setelah pengujian; tidak memakai akun asli. Frontend `npm run test:billing` memeriksa proxy, same-origin POST/PATCH, no-store dan proyeksi respons dengan data sintetis.


## Langganan bulanan (migration 005)

Form menyediakan Sekali Bayar, Cicilan, dan Langganan. `TransactionKind` memakai `ONE_TIME`, `INSTALLMENT`, `SUBSCRIPTION`. Request lama tanpa jenis tetap kompatibel: tenor 0 menjadi ONE_TIME, tenor lainnya INSTALLMENT.

```json
{"TransactionKind":"SUBSCRIPTION","Description":"Apple - Storage 50 GB","Tenor":0,"FirstInstallment":"2026-10-10","Amount":15000,"Notes":""}
```

Untuk langganan, `FirstInstallment` adalah tanggal penagihan pertama (2000-01-01 sampai 9997-12-31), bukan tanggal jatuh tempo. Tenor harus 0 atau dihilangkan, LastInstallment harus null atau dihilangkan. Tidak ada tanggal akhir sampai dihentikan. Response LastInstallment null, TransactionKind SUBSCRIPTION, StoppedOn null saat aktif, NextChargeDate dan NextDueDate untuk penagihan berikutnya. Rincian bulanan memiliki ChargedOn; cicilan lama bernilai null.

GET daftar/detail, pembayaran, perubahan harga, dan penghentian melakukan catch-up tagihan bulanan yang sudah terbit sampai tanggal hari ini UTC+7, dalam lock akun kemudian transaksi PostgreSQL. Unique transaction/sequence menghindari duplikat. Tidak ada scheduler background pada versi ini: jika aplikasi lama tidak dibuka, bulan yang terlewat dibuat saat diakses kembali. Tanggal awal di masa depan belum memiliki tagihan terbit. Hari 29–31 menyesuaikan akhir bulan dan kembali ke anchor semula pada bulan berikutnya.

Aturan awal CC/fixed: biaya pada/sebelum BillingDate masuk periode terbit bulan itu; setelahnya masuk periode bulan depan. DueDate > BillingDate jatuh pada bulan terbit, DueDate <= BillingDate pada bulan setelah terbit. Misalnya BillingDate 3 / DueDate 19 dan biaya 10 Oktober, jatuh tempo 19 November. Untuk akun tanpa tanggal tetap, jatuh tempo mengikuti tanggal penagihan. Kedua hari fixed disnapshot saat langganan dibuat; edit tanggal akun tidak mengubah langganan yang sudah ada.

- PATCH `/billing/transactions/{id}/subscription-amount`, body `{"Amount":20000}`: hanya langganan aktif, tagihan terbit dipertahankan, nominal baru berlaku untuk bulan yang belum terbit.
- POST `/billing/transactions/{id}/stop`, body `{}` melalui BFF: berhenti setelah hari ini, idempotent, tidak menghapus tagihan sampai hari ini atau riwayat pembayaran. Tidak membatalkan langganan di penyedia layanan; pengguna melakukannya sendiri di Apple/penyedia lain.
- Pembayaran tetap berurutan dan tidak dapat dibatalkan. Endpoint last-amount menolak langganan; untuk langganan gunakan perubahan harga berikutnya.
- Delete akun ditolak jika ada langganan aktif, termasuk yang belum mulai atau seluruh tagihannya lunas. Setelah dihentikan dan seluruh tagihan terbit lunas, akun bisa dihapus dengan konfirmasi yang ada.

Kedua endpoint baru memakai JWT aplikasi, owner scope, no-store, dan proxy same-origin yang sama. Tidak ada perubahan penyimpanan nomor kartu/enkripsi.


### Hapus langganan yang dihentikan

DELETE `/billing/transactions/{id}` (BFF path sama di `/api/billing`) hanya menghapus langganan SUBSCRIPTION yang sudah dihentikan dan seluruh tagihan terbitnya lunas. Langganan tanpa tagihan terbit juga boleh dihapus setelah dihentikan. Langganan aktif, cicilan/sekali bayar, atau langganan dengan tagihan belum lunas ditolak 409. Data user lain/tidak ditemukan mendapat 404; sesi tidak valid 401. Lock akun kemudian transaksi menserialisasi delete dengan pembayaran/penghentian/detail. Rincian dan transaksi langganan dihapus bersama dalam satu commit, akun serta transaksi lain tetap tersimpan. Respons 204 no-store; proxy DELETE memeriksa same-origin dan JWT server. UI menampilkan trash di baris langganan, disabled sampai memenuhi syarat, dengan konfirmasi permanen sebelum hapus.


### Filter status dan batas tampilan riwayat

Daftar per akun memiliki Aktif (default), Lunas, dan Semua. Sekali Bayar/Cicilan masuk Lunas jika memiliki tagihan dan seluruh tagihan lunas. Langganan aktif selalu berada di Aktif; setelah dihentikan masuk Lunas hanya jika tidak ada tagihan belum lunas, termasuk langganan yang dihentikan sebelum tanggal mulai.

Riwayat selesai ditampilkan selama 3 bulan kalender sejak pembayaran terakhir, dengan hari akhir bulan dijepit jika diperlukan. Untuk langganan yang dihentikan tanpa tagihan terbit, tanggal berhenti menjadi titik awal. Setelah mencapai batas, riwayat disembunyikan pada ketiga filter FE. Transaksi belum lunas dan langganan aktif tidak dibatasi umur. Data transaksi/rincian/pembayaran tetap tersimpan di database dan tetap tersedia melalui API; tidak ada penghapusan otomatis atau perubahan schema.


### Transaction Date (migration 006)

Form baru mengirim TransactionDate (YYYY-MM-DD, 2000-01-01 sampai 9997-12-31), jenis, tenor, nominal, dan notes. FirstInstallment/LastInstallment dihitung server; jika klien tetap mengirim tanggal tersebut, nilainya harus cocok dengan hasil server. FE menampilkan keduanya readonly. TransactionDate tersimpan dan tersedia di daftar/detail melalui proyeksi respons BFF.

Akun fixed: transaksi pada/sebelum BillingDate memakai bulan terbit yang sama; transaksi setelah BillingDate memakai bulan berikutnya. FirstInstallment = BillingDate pada bulan terbit pertama. Jadwal tagihan bulanan memakai DueDate. Jika DueDate <= BillingDate, jatuh tempo berada pada bulan setelah terbit, selain itu bulan terbit yang sama. LastInstallment = tanggal jatuh tempo tagihan terakhir. Contoh TransactionDate 2026-10-05, BillingDate 3, DueDate 19, tenor 3: FirstInstallment 2026-11-03; LastInstallment 2027-01-19; rincian jatuh tempo 19 Nov, 19 Des, 19 Jan. Akun nonfixed memakai TransactionDate sebagai tanggal pertama dan anchor hari jatuh tempo; tanggal terakhir mengikuti jumlah bulan tenor. Sekali Bayar memiliki satu tagihan. Tanggal 29–31 menyesuaikan akhir bulan tanpa menggeser anchor berikutnya.

Langganan: TransactionDate merupakan tanggal penagihan awal layanan. FirstInstallment menampilkan tanggal terbit pertama akun; LastInstallment tetap null. Pembuatan langganan bulanan memakai TransactionDate sebagai anchor ChargedOn, bukan tanggal terbit, agar tanggal langganan tidak bergeser. Snapshot tanggal akun tetap berlaku.

Data lama TransactionDate null, tidak ditebak dari tanggal cicilan. Jadwal lama dipertahankan. Request klien lama tanpa TransactionDate masih bisa mengirim FirstInstallment/LastInstallment menggunakan aturan sebelumnya; form FE baru selalu mengirim TransactionDate.
