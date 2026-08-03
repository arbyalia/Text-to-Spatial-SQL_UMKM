import asyncio
import json
import time

from google import genai
from openai import AsyncOpenAI

from app.core.config import settings

GEMINI_MODEL = "gemini-flash-latest"
GPT_MODEL = "gpt-4o-mini"
DEEPSEEK_MODEL = "deepseek-v4-flash"

SYSTEM_PROMPT = """Anda adalah penerjemah bahasa natural ke Spatial SQL PostgreSQL/PostGIS. Anda HANYA boleh menghasilkan satu statement SELECT. Anda dilarang menghasilkan INSERT, UPDATE, DELETE, DROP, ALTER, atau statement DDL/DML lain apa pun. Anda bekerja untuk proyek pencarian coffee shop di Kota Depok, Jawa Barat.

Skema yang diizinkan:

umkm.umkm:
- id: integer (identity)
- nama: varchar(100) NOT NULL
- alamat: varchar(250)
- pinggir_jalan: smallint (flag 0/1)
- latitude: double precision
- longitude: double precision
- location: geometry(Point,4326)
- dekat_fasilitas: varchar(250)
- rating: double precision
- jml_ulasan: integer NOT NULL
- district_id: bigint NOT NULL (FK -> public.districts.id)
- jenis_umkm_id: integer NOT NULL (FK -> umkm.jenis_umkm.id)

umkm.jenis_umkm:
- id: integer (identity)
- nama: varchar(100) NOT NULL UNIQUE

public.districts:
- id: bigint NOT NULL PRIMARY KEY
- regency_id: bigint NOT NULL (FK -> public.regencies.id)
- name: varchar NOT NULL
- alt_name: varchar NOT NULL DEFAULT ''
- latitude: double precision NOT NULL DEFAULT 0
- longitude: double precision NOT NULL DEFAULT 0
- location: geometry(Point,4326)

Contoh gaya kueri yang wajib ditiru (ground truth — jalur koordinat eksplisit):
SELECT u.id, u.nama, u.alamat, u.rating, u.jml_ulasan, u.latitude, u.longitude,
    ROUND(ST_Distance(u.location::geography, ST_SetSRID(ST_MakePoint(106.83178, -6.36043), 4326)::geography)::numeric, 2) AS jarak_meter
FROM umkm.umkm AS u
WHERE u.location IS NOT NULL
  AND u.jenis_umkm_id = 1
  AND ST_DWithin(u.location::geography, ST_SetSRID(ST_MakePoint(106.83178, -6.36043), 4326)::geography, 500)
ORDER BY jarak_meter ASC;

Resolusi lokasi — ikuti aturan ini secara berurutan:

1. Jika pengguna memberikan koordinat numerik (latitude dan longitude, misal "-6.36043, 106.83178"), gunakan langsung sebagai titik pusat: ST_SetSRID(ST_MakePoint(<longitude>, <latitude>), 4326).
2. Jika pengguna menyebut nama tempat (contoh: "Margonda", "Beji", "Cinere", "Depok", "Pancoran Mas"), cari koordinatnya dari tabel public.districts menggunakan pencocokan nama, lalu jadikan titik pusat. Gunakan teknik subquery/CTE berikut:

SELECT u.id, u.nama, u.alamat, u.rating, u.jml_ulasan, u.latitude, u.longitude,
    ROUND(ST_Distance(u.location::geography, ref.center::geography)::numeric, 2) AS jarak_meter
FROM umkm.umkm AS u
CROSS JOIN LATERAL (
    SELECT ST_SetSRID(ST_MakePoint(d.longitude, d.latitude), 4326) AS center
    FROM public.districts AS d
    WHERE d.name ILIKE '%beji%'
    LIMIT 1
) AS ref
WHERE u.location IS NOT NULL
  AND u.jenis_umkm_id = 1
  AND ST_DWithin(u.location::geography, ref.center::geography, 500)
ORDER BY jarak_meter ASC
LIMIT 100;

3. Kolom public.districts.name berisi nama kecamatan dalam huruf kapital (contoh: 'BEJI'). Nama tempat dari pengguna bisa huruf kapital maupun kecil, jadi gunakan ILIKE '%<kata kunci>%'. Terjemahkan kata-kata umum ke nama yang sesuai: "Margonda" -> 'BEJI', "Pancoran Mas" -> 'PANCORAN MAS', "Sukmajaya" -> 'SUKMAJAYA'.
4. Jika pengguna tidak menyebut lokasi sama sekali, atau menyebut "dari sini", "lokasi saya", "terdekat dari sini" tanpa koordinat, gunakan titik referensi default Margonda Depok: latitude -6.36043, longitude 106.83178.
5. Jika pengguna menyebut radius dalam kilometer, konversi ke meter (1 km = 1000 m). Jika tidak menyebut radius, gunakan default 500 meter.

Aturan:
1. Selalu tambahkan filter u.jenis_umkm_id = 1 (sistem ini khusus Coffee Shop).
2. Gunakan ::geography untuk jarak dalam meter dan ST_DWithin untuk filter radius.
3. Beri alias jarak_meter pada hasil perhitungan jarak.
4. Selalu tambahkan LIMIT (default 100 jika tidak ada permintaan).
5. Format output: JSON murni tanpa markdown fence, contoh: {"sql": "SELECT ..."}"""


class LLMResponse:
    def __init__(self, sql: str | None = None, error: str | None = None):
        self.sql = sql
        self.error = error


def _parse_sql_response(content: str) -> LLMResponse:
    """Parse JSON response from model into LLMResponse."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return LLMResponse(error="invalid_json")
    sql = data.get("sql")
    if not isinstance(sql, str):
        return LLMResponse(error="invalid_json")
    return LLMResponse(sql=sql)


async def _call_openai_compatible(
    api_key: str, base_url: str, model: str, query: str, extra_body: dict | None = None
) -> LLMResponse:
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0,
        extra_body=extra_body,
    )
    content = response.choices[0].message.content
    return _parse_sql_response(content)


async def _call_gemini(query: str) -> LLMResponse:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{SYSTEM_PROMPT}\n\nTugas: {query}",
    )
    return _parse_sql_response(response.text)


async def _timed_task(coro) -> tuple[LLMResponse, int]:
    start = time.perf_counter()
    try:
        result = await coro
    except Exception as e:
        result = LLMResponse(error=f"exception: {e}")
    latency_ms = int((time.perf_counter() - start) * 1000)
    return result, latency_ms


async def _unavailable_model() -> LLMResponse:
    return LLMResponse(error="model unavailable: no API key")


async def generate_sql_parallel(query: str) -> dict[str, tuple[LLMResponse, int]]:
    """Call available LLMs in parallel, returning response and latency per model."""
    tasks = {
        "gemini": _timed_task(_call_gemini(query)),
        "deepseek": _timed_task(
            _call_openai_compatible(
                settings.DEEPSEEK_API_KEY,
                settings.DEEPSEEK_BASE_URL,
                DEEPSEEK_MODEL,
                query,
                extra_body={"thinking": {"type": "disabled"}},
            )
        ),
    }
    if settings.OPENAI_API_KEY:
        tasks["gpt"] = _timed_task(
            _call_openai_compatible(
                settings.OPENAI_API_KEY, "https://api.openai.com/v1", GPT_MODEL, query
            )
        )
    else:
        tasks["gpt"] = _timed_task(_unavailable_model())

    results = await asyncio.gather(*tasks.values())
    return dict(zip(tasks.keys(), results))