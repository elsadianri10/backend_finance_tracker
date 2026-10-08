# Fee akun Tagihan

MonthlyFee = fee bulanan; PaymentFee = fee sekali per pembayaran total akun. Berlaku pada Credit Card dan Pay Later, default Rp 0. API create/update menerima rupiah bulat 0–1 triliun dan list/detail mengembalikan kedua nilai. Update yang tidak mengirim field fee mempertahankan nilai lama. FE memformat ribuan dan meneruskan angka, bukan string bertanda titik.

Total tabel akun mengikuti filter transaksi yang tampil: subtotal nominal per tagihan + MonthlyFee + PaymentFee. Fee tidak dikalikan jumlah transaksi/cicilan. Rincian fee adalah konfigurasi saat ini; bukan transaksi baru atau bukti pembayaran fee, dan tidak mengubah status pelunasan cicilan. Fee berlaku pada akun, terpisah dari AdminFee/OthersFee di My Bank Account.

Database lama: jalankan 013_billing_account_fees.sql setelah migration 012. Akun lama mendapat fee 0; data lama dipertahankan. Database baru memakai baseline 000 sampai 013. Jangan menjalankan reset pada database berisi data yang ingin dipertahankan.
