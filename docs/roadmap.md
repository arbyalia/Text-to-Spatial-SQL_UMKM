# Roadmap

## Tahap 1: Fondasi (selesai, 10 Oktober 2026)

- [x] Sanitizer diperbaiki: batas radius berlaku, allowlist fungsi, CTE tidak salah blokir, LIMIT dibatasi
- [x] Role read-only diverifikasi saat startup dan memakai URL terpisah
- [x] Pemanggilan LLM diseragamkan (temperature 0, mode JSON, client tunggal) dan model Groq ditambahkan
- [x] API `/api/v1` dengan lokasi pengguna, pilihan model, strategi prompt, dan API key opsional
- [x] Prompt dinamis dari kategori dan kecamatan di database
- [x] Log eksperimen, runner, evaluator, dan uji statistik
- [x] Dataset pilot (20 pertanyaan) dan kasus keamanan (17 kasus)
- [x] Unit test

## Tahap 2: Pilot

- [ ] Isi `GROQ_API_KEY`, jalankan pilot dengan 20 pertanyaan, dan periksa error per model
- [ ] Perbaiki prompt dan dataset berdasarkan hasil pilot (prompt dikunci setelah tahap ini)

## Tahap 3: Dataset final (setelah data dari dosen tersedia)

- [ ] Periksa kualitas data baru (`district_id`, kategori, koordinat)
- [ ] Tambah kategori ke `umkm.jenis_umkm` dan muat data
- [ ] Susun 120–150 pertanyaan dan `gold_sql`, lalu validasi bersama dosen

## Tahap 4: Eksperimen dan analisis

- [ ] Jalankan eksperimen sesuai `docs/protokol_eksperimen.md`
- [ ] Analisis: tabel, grafik, uji signifikansi, analisis error per kategori

## Tahap 5: Publikasi

- [ ] Studi literatur (Text-to-SQL, Text-to-Spatial-SQL, LLM untuk GIS) dan penentuan research gap
- [ ] Pilih jurnal SINTA 3 target dan ikuti template-nya
- [ ] Tulis paper, video demo, submit
