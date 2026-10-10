import httpx
import pandas as pd
import streamlit as st

from app.core.config import settings

BACKEND_API_URL = settings.BACKEND_API_URL
HEADERS = {"X-API-Key": settings.API_KEY} if settings.API_KEY else {}

st.set_page_config(page_title="Text-to-Spatial-SQL UMKM", layout="wide")
st.title("Text-to-Spatial SQL: Pencarian Lokasi UMKM")


@st.cache_data(ttl=60)
def fetch_models() -> list[dict]:
    resp = httpx.get(f"{BACKEND_API_URL}/api/v1/models", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def search(payload: dict) -> dict | None:
    try:
        resp = httpx.post(
            f"{BACKEND_API_URL}/api/v1/search/ai", json=payload, headers=HEADERS, timeout=120
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as e:
        st.error(f"Gagal terhubung ke backend: {e}")
        return None


try:
    models = fetch_models()
except httpx.HTTPError as e:
    st.error(f"Backend tidak dapat dihubungi di {BACKEND_API_URL}: {e}")
    st.stop()

with st.sidebar:
    st.header("Pengaturan")
    available = [m["key"] for m in models if m["available"]]
    selected = st.multiselect("Model", [m["key"] for m in models], default=available)
    strategy = st.radio("Strategi prompt", ["few_shot", "zero_shot"], horizontal=True)
    use_location = st.checkbox("Kirim lokasi pengguna", value=True)
    lat = st.number_input("Latitude", value=-6.36043, format="%.6f", disabled=not use_location)
    lon = st.number_input("Longitude", value=106.83178, format="%.6f", disabled=not use_location)

query = st.text_input(
    "Pertanyaan bahasa natural",
    placeholder="coffee shop rating di atas 4.5 dalam radius 1 km dari sini",
)

if st.button("Cari", type="primary", disabled=not (query and selected)):
    payload = {"query": query, "models": selected, "prompt_strategy": strategy}
    if use_location:
        payload.update(latitude=lat, longitude=lon)
    with st.spinner(f"Menjalankan {len(selected)} model secara paralel..."):
        response = search(payload)

    if response:
        results = response["results"]
        st.subheader("Latensi per model (ms)")
        st.bar_chart(
            pd.DataFrame(
                {
                    "LLM": {k: r["latency"]["llm_ms"] for k, r in results.items()},
                    "Database": {k: r["latency"]["db_ms"] or 0 for k, r in results.items()},
                }
            ),
            stack=True,
        )

        for col, (key, result) in zip(st.columns(len(results)), results.items(), strict=True):
            with col:
                st.subheader(key)
                st.caption(result["model_id"])
                if result["status"] == "success":
                    st.success(f"{result['count']} hasil, {result['latency']['total_ms']} ms")
                    df = pd.DataFrame(result["data"])
                    if {"latitude", "longitude"} <= set(df.columns) and not df.empty:
                        st.map(df.dropna(subset=["latitude", "longitude"]), size=20)
                    st.dataframe(df, width="stretch")
                else:
                    st.error(f"{result['status']}: {result['error_message']}")
                with st.expander("SQL"):
                    st.code(result["sql"] or result["raw_sql"] or "-", language="sql")
