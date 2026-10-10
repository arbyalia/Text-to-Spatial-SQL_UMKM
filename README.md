# Text-to-Spatial SQL UMKM

RESTful API yang menerjemahkan pertanyaan berbahasa Indonesia menjadi Spatial SQL (PostgreSQL/PostGIS) dengan LLM untuk mencari lokasi UMKM. Proyek ini dibuat untuk Tugas Akhir Publikasi Berdampak dengan judul *Pengembangan RESTful API Text-to-Spatial SQL Berbasis LLM untuk Pencarian Lokasi UMKM Menggunakan PostgreSQL PostGIS*.

Proyek ini mencakup:

- API FastAPI `/api/v1` yang menerima pertanyaan, lokasi pengguna (opsional), model, dan strategi prompt.
- SQL hasil LLM diamankan empat lapis: validasi input, validasi struktural `sqlglot`, role database read-only, dan `statement_timeout`.
- Beberapa LLM dipanggil paralel dengan parameter yang identik. Defaultnya tiga model open-weight di Groq.
- Skrip eksperimen dan evaluasi untuk Execution Accuracy, latensi, dan uji signifikansi.
- Dashboard Streamlit untuk demo.

## Menjalankan

Kebutuhan: Python 3.12+, PostgreSQL 15+ dengan PostGIS 3.

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # isi password DB dan GROQ_API_KEY

createdb ta_umkm
PGDATABASE=ta_umkm AI_EXECUTOR_PASSWORD=ganti_password ./db/setup.sh

uvicorn app.main:app --reload            # API di http://localhost:8000, dokumentasi di /docs
streamlit run frontend.py                # dashboard di http://localhost:8501
pytest                                   # unit test, tanpa database
```

Saat startup, API menolak berjalan jika `AI_EXECUTOR_DATABASE_URL` memakai role yang punya hak superuser.

## Endpoint

| Method | Path | Fungsi |
|---|---|---|
| GET | `/health` | Status API dan koneksi database |
| GET | `/api/v1/models` | Daftar model aktif beserta parameternya |
| POST | `/api/v1/search/manual` | Pencarian radius tanpa LLM (baseline) |
| POST | `/api/v1/search/ai` | Text-to-Spatial SQL dengan satu atau beberapa model |

Contoh:

```bash
curl -X POST localhost:8000/api/v1/search/ai -H 'Content-Type: application/json' -d '{
  "query": "coffee shop rating minimal 4.5 dalam 1 km dari sini",
  "latitude": -6.3657, "longitude": 106.8342,
  "models": ["llama-3.3-70b"], "prompt_strategy": "few_shot"
}'
```

Skema request dan response lengkap ada di `/docs` (OpenAPI).

## Eksperimen

```bash
python -m experiments.run_benchmark --dataset experiments/dataset/pilot_questions.jsonl \
    --strategies zero_shot,few_shot --repeats 3 --out experiments/results/pilot.jsonl
python -m experiments.evaluate --dataset experiments/dataset/pilot_questions.jsonl \
    --results experiments/results/pilot.jsonl --out experiments/results/pilot_eval
```

Desain eksperimen ada di [docs/protokol_eksperimen.md](docs/protokol_eksperimen.md).

## Dokumentasi

- [docs/arsitektur.md](docs/arsitektur.md): alur data dan struktur kode
- [docs/database.md](docs/database.md): skema, setup, dan catatan kualitas data
- [docs/keamanan.md](docs/keamanan.md): arsitektur keamanan berlapis
- [docs/protokol_eksperimen.md](docs/protokol_eksperimen.md): pertanyaan penelitian, dataset, metrik, prosedur
- [docs/roadmap.md](docs/roadmap.md): tahapan pengerjaan
