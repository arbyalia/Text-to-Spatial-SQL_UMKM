# Protokol Eksperimen

Dokumen ini menjadi dasar Bab Metode pada paper. Isinya mengikuti keputusan 10 Oktober 2026: penelitian mengukur akurasi, kinerja, dan keamanan; model yang dipakai adalah tiga model open-weight di satu provider (Groq); strategi prompt menjadi variabel kedua.

## Pertanyaan penelitian

1. **RQ1 (akurasi):** Seberapa akurat SQL spasial yang dihasilkan masing-masing LLM dari pertanyaan berbahasa Indonesia, diukur dengan Execution Accuracy?
2. **RQ2 (strategi prompt):** Apakah few-shot meningkatkan akurasi dibanding zero-shot, dan apakah efeknya sama untuk tiap model?
3. **RQ3 (kinerja):** Berapa latensi API (LLM, eksekusi database, total) dan tingkat keberhasilan untuk tiap model?
4. **RQ4 (keamanan):** Seberapa efektif lapisan keamanan terhadap prompt injection dan SQL berbahaya, dan berapa *false positive* pada kueri sah?

## Variabel

| Jenis | Variabel |
|---|---|
| Independen | Model (3 level), strategi prompt (zero-shot, few-shot) |
| Dependen | Execution match, F1 hasil, status (valid/invalid), latensi LLM/DB/total, token |
| Dikontrol | System prompt identik antarmodel (versi dicatat sebagai `PROMPT_VERSION`), `temperature=0`, `max_output_tokens=1024`, `seed=42`, mode JSON, provider dan region sama, skema dan data sama, LIMIT dan timeout sama |

## Model

Daftar model ada di `app/services/model_registry.py`. Nama model dicek di dokumentasi Groq pada 10 Oktober 2026.

| Kunci | Model ID Groq | Catatan |
|---|---|---|
| `llama-3.3-70b` | `llama-3.3-70b-versatile` | Non-reasoning |
| `qwen3.8-27b` | `qwen/qwen3.8-27b` (preview) | Reasoning dimatikan (`reasoning_effort: none`) |
| `gpt-oss-120b` | `openai/gpt-oss-120b` | Reasoning tidak bisa dimatikan; dipakai `reasoning_effort: low` |

Catatan untuk paper: gpt-oss tetap melakukan sedikit reasoning, jadi latensinya tidak sepenuhnya setara. Hal ini perlu ditulis sebagai batasan, atau gpt-oss diganti model non-reasoning jika tersedia saat eksperimen. Model preview bisa berubah atau dihapus, jadi catat tanggal pengujian dan versi persis.

## Dataset uji

Format: JSONL, satu pertanyaan per baris.

```json
{"id": "P001", "category": "radius_koordinat", "difficulty": "mudah",
 "question": "...", "latitude": null, "longitude": null,
 "gold_sql": "SELECT ...", "order_matters": false}
```

- `experiments/dataset/pilot_questions.jsonl`: 20 pertanyaan pilot untuk data coffee shop saat ini. Seluruh `gold_sql` sudah dijalankan di database lokal dan mengembalikan hasil yang tidak kosong.
- `experiments/dataset/security_cases.jsonl`: 17 kasus keamanan.
- Dataset final (target 120–150 pertanyaan) disusun setelah data UMKM final tersedia, dengan sebaran kategori:

| Kategori | Porsi |
|---|---|
| radius_koordinat | 15% |
| radius_lokasi_pengguna | 15% |
| radius_nama_tempat | 15% |
| k_terdekat | 15% |
| filter_atribut (rating, ulasan, fasilitas, pinggir jalan, kategori UMKM) | 20% |
| agregasi | 10% |
| bahasa_informal | 10% |

Aturan penyusunan:

- Pertanyaan uji tidak boleh sama dengan contoh few-shot di `app/services/prompt.py`.
- `gold_sql` ditulis manual dan divalidasi oleh dua orang (penulis dan dosen pembimbing) agar bisa dilaporkan sebagai ground truth yang terverifikasi.
- Untuk pertanyaan ambigu (misalnya "rating bagus"), definisi ditetapkan di awal (misalnya rating ≥ 4.5) dan dicatat.

## Metrik

| Metrik | Definisi |
|---|---|
| Execution Accuracy (EX) | Proporsi percobaan yang hasil eksekusinya sama dengan hasil `gold_sql`. Jika kedua hasil punya kolom `id`, dibandingkan himpunan `id` (kolom tambahan diabaikan). Jika tidak, dibandingkan multiset nilai baris (nama kolom diabaikan; semua angka, baik integer, float, maupun Decimal, diubah ke float dan dibulatkan 2 desimal sehingga 19 dan 19.0 dianggap sama). Untuk `order_matters: true`, urutan juga harus sama |
| Precision/Recall/F1 | Kecocokan sebagian antara hasil model dan ground truth |
| Valid SQL Rate | Proporsi SQL yang lolos sanitizer (status `success` atau `db_execution_error`) |
| JSON strict rate | Proporsi output yang langsung berupa JSON valid tanpa perbaikan |
| Latensi | Median dan p95 untuk `llm_ms`, `db_ms`, `total_ms`, dan `http_ms` (diukur dari sisi klien) |
| Token | Rata-rata token input dan output |
| Keamanan | Distribusi status untuk kasus keamanan; serangan dihitung berhasil jika ada SQL yang menulis data atau membaca di luar tabel yang diizinkan |

Uji statistik (dihitung otomatis oleh `experiments/evaluate.py`):

- Antarmodel, per strategi: Cochran's Q, dilanjutkan McNemar exact berpasangan.
- Antarstrategi, per model: McNemar exact.
- Correctness per pertanyaan ditentukan dengan suara mayoritas dari beberapa ulangan: pertanyaan dianggap benar jika benar pada lebih dari separuh ulangan (> 0,5).
- Jumlah ulangan harus ganjil (1, 3, 5, ...) supaya suara mayoritas tidak pernah seri. `run_benchmark.py` memberi peringatan jika `--repeats` genap.

## Prosedur

1. Jalankan API dengan `EXPERIMENT_LOG_PATH` aktif.
2. `python -m experiments.run_benchmark ...`: setiap request hanya meminta satu model, urutan percobaan diacak (seed tetap), dan percobaan yang sudah selesai dilewati jika skrip dijalankan ulang.
3. `python -m experiments.evaluate ...` menghasilkan `attempts.csv`, `summary.csv`, `status_counts.csv`, `accuracy_by_category.csv`, dan `significance.json`.

## Anggaran kuota (Groq free tier)

Per Oktober 2026, batas untuk `gpt-oss-120b` dan `qwen3.8-27b` adalah 30 RPM, 1.000 RPD, 8.000 TPM, dan 200.000 TPD. Batas ini berlaku per model, sehingga ketiga model bisa dijalankan bersamaan. Batas `llama-3.3-70b-versatile` perlu dicek di halaman limits akun.

Prompt few-shot berukuran sekitar 1.300 token, jadi satu percobaan memakan kira-kira 1.500 token. Dengan 200.000 TPD, satu model bisa menjalankan sekitar 130 percobaan per hari. Batas 8.000 TPM juga berarti jeda antar-request minimal sekitar 12 detik (`--delay 12`).

Rencana yang muat di free tier:

| Tahap | Percobaan per model | Perkiraan waktu |
|---|---|---|
| Akurasi: 150 pertanyaan × 2 strategi × 1 ulangan (temperature 0) | 300 | 2–3 hari |
| Konsistensi dan latensi: 30 pertanyaan terstratifikasi × 2 strategi × 5 ulangan | 300 | 2–3 hari |
| Keamanan: 17 kasus × 2 strategi × 1 ulangan | 34 | < 1 hari |

Cek ulang batas di https://console.groq.com/settings/limits sebelum eksperimen final.

## Riwayat perubahan protokol

Setiap perubahan prompt, parameter model, sanitizer, atau metrik dicatat di sini. `PROMPT_VERSION` (di `app/services/prompt.py`) ikut tercatat di response `/api/v1/search/ai`, log JSONL, dan setiap baris output `run_benchmark.py`, sehingga hasil dari versi berbeda tidak tercampur.

### 10 Oktober 2026, prompt `v2-2026-10-10`

1. Contoh few-shot pertama: kata "kafe" di pertanyaan diganti nama kategori `FEW_SHOT_CATEGORY` dari katalog dalam huruf kecil (saat ini "coffee shop"), atau "UMKM" jika kategori itu tidak ada. SQL contoh dan bagian prompt lain tidak berubah. Hasil eksperimen dengan prompt `v1-2026-10-10` tidak boleh digabung dengan hasil `v2-2026-10-10`.

### 10 Oktober 2026, prompt `v1-2026-10-10`

1. Sanitizer, batas radius: `ST_DWithin` wajib memakai geography pada dua argumen pertamanya dan radiusnya harus konstanta numerik ≤ 5000 m (aritmetika antar-konstanta boleh). Batas yang sama berlaku untuk perbandingan `ST_Distance` dengan konstanta (`<`, `<=`, `BETWEEN`) di `WHERE`, `HAVING`, dan `JOIN ... ON`, yang juga wajib memakai geography.
2. Sanitizer, set operation: `UNION`, `UNION ALL`, `INTERSECT`, dan `EXCEPT` diizinkan jika setiap cabang SELECT dan lolos semua cek. LIMIT diterapkan di level terluar.
3. Metrik: semua angka (int, float, Decimal, bukan bool) dinormalisasi menjadi `round(float(v), 2)`, sehingga 19 dan 19.0 dianggap sama.
4. Suara mayoritas memakai > 0,5 (sebelumnya ≥ 0,5). Jumlah ulangan harus ganjil; `run_benchmark.py` memberi peringatan jika `--repeats` genap.
5. Contoh few-shot: contoh pertama memakai kategori dari `FEW_SHOT_CATEGORY` (default "Coffee Shop"); jika kategori itu tidak ada di katalog, contoh ditulis tanpa filter kategori dan pertanyaannya memakai "UMKM". Contoh ketiga (`JOIN districts ON district_id`) diganti dengan "jumlah UMKM per kategori dalam radius 2 km dari koordinat -6.40, 106.80" (`JOIN umkm.jenis_umkm`, `GROUP BY` nama kategori, `ST_DWithin` dengan geography). Teks radius maksimum di aturan prompt diformat dari `MAX_RADIUS_METER`. Bagian prompt lain tidak berubah; dengan katalog saat ini, satu-satunya perbedaan teks prompt adalah contoh ketiga.
6. Parameter model, identik untuk semua model: `max_output_tokens = 1024` dan `seed = 42` (dikirim sebagai `max_completion_tokens` dan `seed` ke provider OpenAI-compatible, `max_output_tokens` dan `seed` ke Gemini), di samping `temperature = 0`.
7. Ketertelusuran: `PROMPT_VERSION = "v1-2026-10-10"` dicatat di response API, log JSONL, dan output benchmark.
8. Sanitizer: statement penulisan atau DDL (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `CREATE`, `DROP`, `ALTER`, `TRUNCATE`, `COPY`, `GRANT`, `SET`) ditolak di mana pun dalam kueri, termasuk di dalam CTE (`WITH d AS (DELETE ... RETURNING id) SELECT ...`). Sebelumnya bentuk ini lolos lapis 2 dan baru diblokir lapis 3. Prompt tidak berubah.

## Ancaman validitas

- Latensi API cloud dipengaruhi beban server dan jaringan. Mitigasinya: urutan percobaan diacak, satu provider dan lokasi klien yang sama, dan yang dilaporkan median/p95.
- Data terbatas pada satu kota dan beberapa kategori UMKM.
- Resolusi lokasi berbasis titik pusat kecamatan, bukan poligon.
- Kualitas `district_id` pada data (lihat `docs/database.md`).
