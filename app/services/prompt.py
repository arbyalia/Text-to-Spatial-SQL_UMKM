from typing import Literal

from app.core.config import settings
from app.core.security import MAX_RADIUS_METER
from app.services.catalog import Catalog

PromptStrategy = Literal["zero_shot", "few_shot"]

PROMPT_VERSION = "v2-2026-10-10"

SCHEMA = """umkm.umkm (data UMKM):
- id: integer, primary key
- nama: varchar(100)
- alamat: varchar(250)
- pinggir_jalan: smallint (1 = di pinggir jalan besar, 0 = tidak)
- latitude, longitude: double precision
- location: geometry(Point, 4326)
- dekat_fasilitas: varchar(250), teks bebas dipisah ". ", nilai yang ada: 'Stasiun / Halte', 'Mall / Pusat perbelanjaan', 'Kampus / Sekolah', 'Perkantoran', 'Tidak Ada'
- rating: double precision (skala 1-5)
- jml_ulasan: integer (jumlah ulasan)
- district_id: bigint -> public.districts.id
- jenis_umkm_id: integer -> umkm.jenis_umkm.id

umkm.jenis_umkm (kategori UMKM):
- id: integer, primary key
- nama: varchar(100)

public.districts (kecamatan):
- id: bigint, primary key
- regency_id: bigint (kabupaten/kota)
- name: varchar, huruf kapital, contoh 'PANCORAN MAS'
- latitude, longitude: double precision (titik pusat kecamatan)
- location: geometry(Point, 4326)"""

RULES = """Aturan:
1. Hasilkan tepat satu statement SELECT. Dilarang INSERT, UPDATE, DELETE, DDL, atau lebih dari satu statement.
2. Gunakan hanya tabel pada skema di atas.
3. Hitung jarak dalam meter dengan cast ::geography. Filter radius wajib memakai ST_DWithin, bukan ST_Distance di WHERE.
4. Jika jarak dihitung, beri alias jarak_meter dengan ROUND(...::numeric, 2) dan urutkan dari yang terdekat.
5. Selalu sertakan kolom u.id, u.nama, u.alamat, u.rating, u.jml_ulasan, u.latitude, u.longitude jika mengembalikan daftar UMKM.
6. Titik pusat pencarian:
   a. Jika pesan berisi "Lokasi pengguna", gunakan koordinat itu: ST_SetSRID(ST_MakePoint(<longitude>, <latitude>), 4326).
   b. Jika pengguna menyebut koordinat, gunakan koordinat tersebut.
   c. Jika pengguna menyebut nama kecamatan, ambil titik pusatnya dari public.districts dengan d.regency_id = {regency_id} dan d.name ILIKE '%<nama>%'.
   d. Jika tidak ada lokasi sama sekali, gunakan titik default: latitude {lat}, longitude {lon}.
7. Radius: konversi kilometer ke meter. Jika radius tidak disebut, gunakan {radius} meter. Radius maksimum {max_radius} meter.
8. Filter kategori dengan u.jenis_umkm_id hanya jika pengguna menyebut jenis UMKM. Gunakan id dari daftar kategori.
9. Selalu tambahkan LIMIT (default 100) kecuali kueri agregasi.
10. Jawab hanya dengan JSON murni tanpa markdown: {{"sql": "SELECT ..."}}"""

FEW_SHOT_EXAMPLES = [
    (
        "{subject} dalam radius 1 km dari koordinat -6.39, 106.82",
        "SELECT u.id, u.nama, u.alamat, u.rating, u.jml_ulasan, u.latitude, u.longitude, "
        "ROUND(ST_Distance(u.location::geography, ST_SetSRID(ST_MakePoint(106.82, -6.39), 4326)::geography)::numeric, 2) AS jarak_meter "
        "FROM umkm.umkm AS u WHERE u.location IS NOT NULL {category_filter}"
        "AND ST_DWithin(u.location::geography, ST_SetSRID(ST_MakePoint(106.82, -6.39), 4326)::geography, 1000) "
        "ORDER BY jarak_meter ASC LIMIT 100",
    ),
    (
        "3 UMKM terdekat dari pusat kecamatan Cilodong",
        "SELECT u.id, u.nama, u.alamat, u.rating, u.jml_ulasan, u.latitude, u.longitude, "
        "ROUND(ST_Distance(u.location::geography, ref.center::geography)::numeric, 2) AS jarak_meter "
        "FROM umkm.umkm AS u CROSS JOIN LATERAL (SELECT d.location AS center FROM public.districts AS d "
        "WHERE d.regency_id = {regency_id} AND d.name ILIKE '%cilodong%' LIMIT 1) AS ref "
        "WHERE u.location IS NOT NULL ORDER BY u.location <-> ref.center LIMIT 3",
    ),
    (
        "jumlah UMKM per kategori dalam radius 2 km dari koordinat -6.40, 106.80",
        "SELECT j.nama AS kategori, COUNT(*) AS jumlah FROM umkm.umkm AS u "
        "JOIN umkm.jenis_umkm AS j ON j.id = u.jenis_umkm_id "
        "WHERE u.location IS NOT NULL "
        "AND ST_DWithin(u.location::geography, ST_SetSRID(ST_MakePoint(106.80, -6.40), 4326)::geography, 2000) "
        "GROUP BY j.nama ORDER BY jumlah DESC",
    ),
]


def few_shot_examples(catalog: Catalog) -> list[tuple[str, str]]:
    """Fill the example templates; the category filter needs a FEW_SHOT_CATEGORY in the catalog."""
    category_id, category = next(
        (
            (cid, name)
            for cid, name in catalog.categories.items()
            if name.lower() == settings.FEW_SHOT_CATEGORY.lower()
        ),
        (None, None),
    )
    values = {
        "subject": "UMKM" if category is None else category.lower(),
        "category_filter": "" if category_id is None else f"AND u.jenis_umkm_id = {category_id} ",
        "regency_id": settings.STUDY_AREA_REGENCY_ID,
    }
    return [(q.format(**values), sql.format(**values)) for q, sql in FEW_SHOT_EXAMPLES]


def build_system_prompt(catalog: Catalog, strategy: PromptStrategy) -> str:
    categories = "\n".join(f"- {cid}: {name}" for cid, name in catalog.categories.items())
    districts = ", ".join(catalog.districts)
    rules = RULES.format(
        regency_id=settings.STUDY_AREA_REGENCY_ID,
        lat=settings.DEFAULT_CENTER_LAT,
        lon=settings.DEFAULT_CENTER_LON,
        radius=settings.DEFAULT_RADIUS_M,
        max_radius=MAX_RADIUS_METER,
    )
    parts = [
        "Anda adalah penerjemah pertanyaan berbahasa Indonesia menjadi Spatial SQL "
        f"PostgreSQL/PostGIS untuk pencarian lokasi UMKM di {settings.STUDY_AREA_NAME}.",
        f"Skema database:\n{SCHEMA}",
        f"Kategori UMKM (umkm.jenis_umkm):\n{categories or '- (kosong)'}",
        f"Kecamatan di wilayah studi (regency_id = {settings.STUDY_AREA_REGENCY_ID}): {districts}",
        rules,
    ]
    if strategy == "few_shot":
        examples = "\n\n".join(
            f'Pertanyaan: {q}\nJawaban: {{"sql": "{sql}"}}' for q, sql in few_shot_examples(catalog)
        )
        parts.append(f"Contoh:\n\n{examples}")
    return "\n\n".join(parts)


def build_user_message(query: str, latitude: float | None, longitude: float | None) -> str:
    if latitude is None or longitude is None:
        return query
    return f"Lokasi pengguna: latitude {latitude}, longitude {longitude}\nPertanyaan: {query}"
