# Passkey dan pemulihan akun

Google tetap menjadi identitas akun. Setelah pengguna mendaftarkan passkey lewat Profil Saya > Keamanan, login Google hanya menghasilkan token sementara selama 5 menit. Token ini bertipe `passkey_pending`, disimpan dalam cookie HttpOnly `finance_pending`, dan tidak diterima endpoint keuangan/profil. Verifikasi WebAuthn atau kode pemulihan sekali pakai baru menghasilkan sesi penuh.

## Deployment

1. Upgrade database yang belum pada versi 021 dengan `database/021_passkeys.sql`, atau jalankan `.\.venv\Scripts\python.exe tests/check_passkey_migration.py --apply` setelah konfigurasi database diarahkan ke tujuan. Script membackup dan membandingkan semua record sebelum commit. Jangan menjalankan baseline 000 pada database aplikasi yang berisi data. Hentikan sementara API lama saat upgrade.
2. Set environment **backend Vercel**:

```dotenv
WEBAUTHN_RP_ID=frontend-finance-tracker-ecru.vercel.app
WEBAUTHN_ORIGINS=https://frontend-finance-tracker-ecru.vercel.app
```

3. Deploy backend (requirements mencakup `webauthn==2.8.0`) dan frontend terbaru. Jangan memakai domain backend untuk RP ID. Jangan memakai wildcard origin atau `vercel.app` sebagai RP ID. RP ID adalah host frontend yang tepat, tanpa protokol/path. Origin harus tepat, termasuk HTTPS.
4. Login Google seperti biasa, lalu buka Profil Saya > Keamanan > Tambah Passkey. Simpan delapan kode pemulihan yang ditampilkan satu kali. Logout, login Google lagi, dan verifikasi passkey. Coba membatalkan verifikasi untuk memastikan tetap di layar login.

Akun tanpa passkey tetap dapat login Google seperti sebelumnya. Pengaktifan passkey mencabut sesi sebelumnya dan menerbitkan sesi baru untuk perangkat pendaftaran. Tidak ada perubahan/backfill transaksi finansial.

## Local dan preview

Konfigurasi lokal pada `.env` memakai `WEBAUTHN_RP_ID=localhost` dan `WEBAUTHN_ORIGINS=http://localhost:3000`. Buka FE dengan **localhost**, bukan 127.0.0.1. Restart backend setelah mengubah environment. Akun/database pengujian sebaiknya terpisah dari produksi; passkey localhost tidak berlaku pada domain produksi. Preview Vercel memerlukan RP/origin tetap tersendiri, bukan wildcard URL deployment. Origin dari header browser tidak dipakai untuk menentukan domain yang dipercaya.

## Penyimpanan dan perlindungan

- `users.auth_version` mencabut sesi saat menambah/menghapus passkey, menggunakan kode pemulihan, atau membuat kode baru. Token lama tanpa `ver` hanya diterima saat versi akun masih 0.
- `user_passkeys` menyimpan ID credential/public key sebagai BYTEA, nama perangkat, domain, counter, status backup, dan waktu penggunaan. Private key/PIN/biometrik tidak disimpan server. Metadata JSON dari browser tidak disimpan sebagai kolom JSON/JSONB.
- `passkey_challenges` berisi nonce acak, pemilik, tujuan LOGIN/REGISTER/MANAGE, versi akun, kedaluwarsa, status penggunaan dan jumlah percobaan. Challenge sekali pakai; maksimum 5 percobaan, 10 challenge aktif per akun. Challenge LOGIN terikat ke token sementara lewat `jti`; operasi diserialisasi dengan lock pengguna/challenge. Challenge kedaluwarsa dibersihkan saat membuat challenge berikutnya.
- Signature, challenge, origin, RP ID, user verification/presence, credential ownership, user handle dan counter diverifikasi oleh library WebAuthn. Operasi keamanan perlu verifikasi baru (maksimum 5 menit); frontend meminta verifikasi ulang bila perlu. Penambahan pertama memerlukan sesi Google baru.
- `passkey_recovery_codes` menyimpan HMAC SHA-256 dari kode acak 128 bit, waktu dibuat/dipakai; tidak ada kode plaintext di DB. Kode hanya dipakai setelah Google berhasil. Satu kode hanya bisa digunakan satu kali. Membuat kode baru menonaktifkan kode lama dan mencabut sesi lain.
- Passkey terakhir tidak dapat dihapus. Untuk mengganti perangkat yang hilang: login Google + kode pemulihan, tambahkan passkey baru, kemudian hapus passkey lama. Maksimum 10 passkey per akun.
- FE hanya menyimpan token dalam cookie HttpOnly/Secure/SameSite=Lax. Respons no-store, mutasi memeriksa same-origin. Token/keys/hash internal tidak diproyeksikan ke browser. Logout menghapus cookie penuh dan sementara; handoff profil hanya dilakukan setelah verifikasi selesai.

## Verifikasi

- Enam tes passkey memakai authenticator perangkat lunak dengan signature ECDSA/CBOR nyata: enrollment, login, penolakan UV/origin/RP/owner/expiry, replay, kode pemulihan, pencabutan sesi dan penghapusan antar pengguna.
- Seluruh 96 tes backend lolos pada suite penuh; keenam tes passkey final juga lolos setelah tambahan kasus signature rusak dan verifikasi ulang. Upgrade 021 dan baseline/reset diuji pada schema PostgreSQL sintetis; upgrade database proyek memakai backup dan seluruh record lama identik.
- Build produksi, TypeScript, lint, tes cookie/proxy, konversi binary WebAuthn, pembatalan, re-verifikasi, serta regresi login/sesi FE lolos.
- Prompt/penyimpanan passkey pada perangkat fisik pengguna perlu direview setelah deploy; tes tidak mendaftarkan passkey pada perangkat atau akun nyata.

Referensi library: https://github.com/duo-labs/py_webauthn dan https://duo-labs.github.io/py_webauthn/registration.html.
