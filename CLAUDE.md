# Panduan untuk AI coding agent

- Bahasa komunikasi dengan pemilik proyek: Bahasa Indonesia. Kode, nama variabel, dan pesan commit dalam bahasa Inggris.
- Kode ringkas dan self-explanatory. Jangan pakai emoji. Komentar hanya untuk hal yang tidak jelas dari kodenya.
- Stack sudah ditentukan dosen: Python, FastAPI, PostgreSQL/PostGIS, Streamlit.
- SQL dari LLM tidak boleh dieksekusi selain lewat `app/core/security.py` (`validate_sql` lalu `execute_ai_sql`).
- Semua model harus dipanggil dengan parameter identik. Perubahan pada prompt atau parameter model memengaruhi validitas eksperimen, jadi catat perubahan itu di `docs/protokol_eksperimen.md`.
- Jalankan `pytest` sebelum commit.
- Dokumentasi: `README.md` dan `docs/`.
