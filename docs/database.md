# Database

## Setup

`db/setup.sh` membangun database dari nol:

1. `db/01_init.sql`: ekstensi PostGIS, schema `umkm`, tabel `umkm.jenis_umkm` (isi awal: `1 = Coffee Shop`).
2. `scripts/load_wilayah.py`: tabel wilayah `provinces → regencies → districts → villages` dari `yusufsyaifudin/wilayah-indonesia`, ditambah kolom `location geometry(Point, 4326)`.
3. `backup_umkm.sql`: tabel `umkm.umkm` (240 coffee shop di Kota Depok).
4. `db/02_readonly_role.sql`: role `readonly_ai_executor` (hanya `SELECT`, default transaksi read-only, timeout 5 detik).

## Skema yang dipakai LLM

| Tabel | Kolom penting |
|---|---|
| `umkm.umkm` | `id, nama, alamat, pinggir_jalan (0/1), latitude, longitude, location, dekat_fasilitas, rating, jml_ulasan, district_id, jenis_umkm_id` |
| `umkm.jenis_umkm` | `id, nama` |
| `public.districts` | `id, regency_id, name (kapital), latitude, longitude, location` (titik pusat kecamatan) |

Index GiST pada `umkm.umkm.location` dipakai oleh `ST_DWithin`.

## Catatan kualitas data (per 10 Oktober 2026)

Hasil pemeriksaan pada data coffee shop saat ini. Data final perlu dicek dengan cara yang sama.

1. **`district_id` tidak cocok dengan tabel wilayah.** Kode `3276061` (CINERE di tabel `districts`) juga dipakai untuk UMKM yang alamatnya di Kecamatan Beji (28 baris, kode BEJI di tabel adalah `3276050`) dan di Kecamatan Sawangan (19 baris, kode SAWANGAN adalah `3276010`). Akibatnya, 104 UMKM tercatat di "Cinere", sedangkan Beji dan Sawangan masing-masing 0. Kemungkinan dataset UMKM memakai versi kode Kemendagri yang berbeda dari tabel wilayah. Selama ini belum diperbaiki, pertanyaan berbasis keanggotaan kecamatan (`JOIN districts ON district_id`) akan memberi jawaban salah. Jalankan `python -m scripts.check_data_quality` untuk memeriksa ulang setelah data diganti.
2. Jika ditentukan dari kecamatan terdekat secara spasial, sebaran data menjadi: Beji 60, Pancoran Mas 34, Cimanggis 31, Sukma Jaya 25, Cinere 19, Bojongsari 16, Sawangan 15, Cilodong 15, Tapos 14, Limo 11.
3. Nama kecamatan tidak unik secara nasional. `BEJI` juga ada di Kabupaten Pasuruan (`3514140`), jadi pencarian nama kecamatan wajib difilter `regency_id = 3276`. System prompt versi lama tidak memakai filter ini, sehingga bisa memilih Beji yang salah.
4. `villages.latitude/longitude` bernilai 0 di sumber data, jadi tabel desa tidak bisa dipakai untuk pencarian spasial.
5. `districts` hanya berisi titik pusat, bukan poligon batas. "Di dalam kecamatan X" hanya bisa didekati dengan `district_id` (lihat poin 1) atau radius dari titik pusat.
6. `dekat_fasilitas` adalah teks bebas dengan nilai: Stasiun / Halte, Mall / Pusat perbelanjaan, Kampus / Sekolah, Perkantoran, Tidak Ada.

Saran untuk dataset final: cocokkan `district_id` dengan versi tabel wilayah yang dipakai (atau ganti tabel wilayah ke versi kode yang sama), dan jika memungkinkan sertakan poligon batas kecamatan.
