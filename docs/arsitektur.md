# Arsitektur Sistem

## Alur data

```
Klien (Streamlit / skrip eksperimen / aplikasi lain)
  │  POST /api/v1/search/ai {query, latitude?, longitude?, models?, prompt_strategy?}
  ▼
FastAPI
  │  Lapis 1: validasi request (Pydantic)
  │  Prompt dibangun dari skema, kategori di umkm.jenis_umkm, dan kecamatan di wilayah studi
  ▼
asyncio.gather ── model 1 ── model 2 ── model 3   (client async, parameter identik)
  │  per model:
  │    LLM ──► {"sql": ...}
  │    Lapis 2: sqlglot (SELECT tunggal, allowlist tabel/fungsi, batas radius, LIMIT)
  │    Lapis 3+4: eksekusi lewat role read-only, transaksi READ ONLY, statement_timeout
  ▼
Respons per model: status, SQL, latensi (llm/db/total), token, data
  │  (opsional) satu baris JSON per request ke EXPERIMENT_LOG_PATH
  ▼
Klien
```

Streamlit hanya klien HTTP. Seluruh logika LLM, keamanan, dan database ada di backend.

## Struktur kode

```
app/
  main.py                  lifespan: verifikasi role executor, muat katalog kategori/kecamatan
  core/
    config.py              pengaturan dari .env
    database.py            engine utama (superuser/owner, hanya untuk endpoint manual dan katalog)
    security.py            sanitizer sqlglot dan eksekusi read-only
    auth.py                header X-API-Key opsional
    experiment_log.py      log JSONL per request
  services/
    model_registry.py      daftar model, provider, dan parameter
    llm_service.py         pemanggilan LLM dan parsing JSON
    prompt.py              system prompt zero-shot / few-shot
    catalog.py             kategori UMKM dan kecamatan dari database
    search_pipeline.py     LLM -> sanitizer -> eksekusi untuk satu model
  routes/                  health, search_manual, search_ai
db/                        skrip setup database
experiments/               dataset, runner, evaluator, metrik
frontend.py                dashboard Streamlit
tests/                     unit test
```

## Keputusan desain

| Keputusan | Alasan |
|---|---|
| FastAPI, PostgreSQL/PostGIS, Streamlit | Ditentukan dosen pembimbing |
| SQLAlchemy async + asyncpg | Driver sync memblokir event loop saat beberapa LLM dipanggil paralel |
| Client LLM dibuat sekali (cache) | Latensi tidak ikut mengukur setup koneksi TLS |
| Semua model memakai `temperature=0`, mode JSON, prompt identik | Variabel independen hanya model dan strategi prompt |
| Model dikonfigurasi lewat `model_registry.py` + `LLM_MODELS` | Menambah atau mengganti model tanpa mengubah kode endpoint |
| Kategori dan kecamatan dimuat dari database | Prompt otomatis ikut berubah saat dataset UMKM bertambah kategori |
| Lokasi pengguna dikirim klien | "Terdekat dari sini" memakai koordinat nyata, bukan titik default |
