import os

import httpx
import pandas as pd
import streamlit as st

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

MODEL_NAMES = ["deepseek", "gpt", "gemini"]
MODEL_LABELS = {"deepseek": "DeepSeek", "gpt": "GPT", "gemini": "Gemini"}

st.set_page_config(page_title="Text-to-Spatial-SQL UMKM", layout="wide")
st.title("Komparasi Model AI: Text-to-Spatial-SQL (Coffee Shop Depok)")

query = st.text_input("Masukkan pertanyaan bahasa natural:", placeholder="cari coffee shop terdekat dari sini radius 500 meter")


def fetch_ai_results(user_query: str) -> dict | None:
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{BACKEND_API_URL}/search/ai",
                json={"query": user_query},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        st.error(f"Gagal terhubung ke backend: {e}")
        return None


ERROR_MESSAGES = {
    "model unavailable: no API key": "API key belum diatur",
}


def summarize(result: dict) -> str:
    status = result["status"]
    if status == "success":
        count = len(result["data"])
        return f"{count} coffee shop ditemukan ({result['latency_ms']}ms)"
    return ERROR_MESSAGES.get(result.get("error_message") or "", status)


if st.button("Cari", type="primary") and query:
    with st.spinner("Menjalankan 3 model LLM secara paralel..."):
        response = fetch_ai_results(query)

    if response:
        results = response.get("results", {})

        latencies = {
            MODEL_LABELS[model]: results[model]["latency_ms"]
            for model in MODEL_NAMES
            if model in results
        }
        if latencies:
            st.subheader("Perbandingan Latensi")
            latency_df = pd.DataFrame(
                [{"Model": k, "Latency (ms)": v} for k, v in latencies.items()]
            )
            st.bar_chart(latency_df.set_index("Model"))

        cols = st.columns(len(MODEL_NAMES))
        for col, model in zip(cols, MODEL_NAMES):
            with col:
                if model not in results:
                    st.subheader(MODEL_LABELS[model])
                    st.warning("Tidak ada hasil.")
                    continue

                result = results[model]
                status = result["status"]
                st.subheader(f"{MODEL_LABELS[model]} — {summarize(result)}")

                if status == "success":
                    if result["data"]:
                        df = pd.DataFrame(result["data"])
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("Tidak ada coffee shop ditemukan dalam radius.")
                    if result["sql"]:
                        with st.expander("SQL mentah"):
                            st.code(result["sql"], language="sql")
                else:
                    st.error(f"Status: {status}")
                    if result["error_message"]:
                        st.write(
                            ERROR_MESSAGES.get(
                                result["error_message"], result["error_message"]
                            )
                        )
                    with st.expander("Detail"):
                        st.write("SQL:", result["sql"])
                        st.write("Data:", result["data"])
else:
    st.info("Masukkan query di atas untuk membandingkan hasil Gemini, GPT, dan DeepSeek.")
