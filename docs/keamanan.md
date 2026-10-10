# Keamanan Berlapis

Sistem ini mengeksekusi SQL yang ditulis model AI eksternal, jadi SQL tersebut diperlakukan sebagai input tidak tepercaya. Blocklist kata kunci (DROP, DELETE) tidak cukup karena mudah disamarkan dan tidak menangkap kueri berbahaya yang tidak memakai kata itu, seperti `SELECT pg_read_file(...)`. Karena itu dipakai empat lapis yang saling independen.

| Lapis | Implementasi | Menangkap |
|---|---|---|
| 1. Validasi request | Pydantic: panjang query ≤ 500, koordinat valid, model dan strategi dikenal; API key opsional; rate limit per menit | Input rusak, request berlebihan, penyalahgunaan kuota LLM |
| 2. Validasi struktural | `app/core/security.py` dengan `sqlglot` | Multi-statement, non-SELECT, `SELECT INTO`, `FOR UPDATE`, tabel di luar allowlist, fungsi di luar allowlist (`pg_sleep`, `pg_read_file`, `dblink`, `set_config`, ...), radius `ST_DWithin` > 5000 m, LIMIT tidak ada atau > 500 |
| 3. Hak akses database | Role `readonly_ai_executor`: hanya `SELECT` pada 6 tabel, `default_transaction_read_only`, transaksi `READ ONLY`. API menolak startup jika role ini superuser | Apa pun yang lolos lapis 2 tetap tidak bisa menulis atau membaca tabel lain |
| 4. Batas waktu | `SET LOCAL statement_timeout` (default 5000 ms) | Kueri berat atau sengaja diperlambat |

Seluruh API memakai satu koneksi database, yaitu `readonly_engine` di `app/core/database.py` (`AI_EXECUTOR_DATABASE_URL`, role `readonly_ai_executor`). Ini berlaku untuk SQL dari LLM, `/api/v1/search/manual`, `/health`, dan pemuatan katalog saat startup. Kredensial owner (`DATABASE_URL`) hanya dipakai skrip di `scripts/` dan tidak dibutuhkan untuk menjalankan API, sehingga kebocoran konfigurasi server API tidak memberi akses tulis ke database.

Allowlist fungsi: semua fungsi PostGIS (`st_*`), fungsi SQL standar yang dikenali `sqlglot` (COUNT, ROUND, AVG, ...), dan beberapa fungsi string/JSON. Fungsi lain ditolak.

Pengujian:

- `tests/test_security.py`: 16 kasus SQL berbahaya yang harus diblokir dan 5 kueri sah yang harus lolos (termasuk CTE, yang sebelumnya salah diblokir).
- `tests/test_readonly_engine.py` dan `tests/integration/test_database.py`: endpoint API hanya memakai `readonly_engine`, dan role read-only cukup untuk `/health` serta `/api/v1/search/manual`.
- `experiments/dataset/security_cases.jsonl`: 17 input bahasa natural berupa prompt injection dan pertanyaan di luar cakupan. Input ini dijalankan lewat runner untuk mengukur di lapis mana serangan berhenti.

Batasan yang perlu disebut di paper: lapis 2 tidak bisa membuktikan bahwa SQL *benar*, hanya bahwa SQL *aman*. Kebenaran diukur terpisah lewat Execution Accuracy.
