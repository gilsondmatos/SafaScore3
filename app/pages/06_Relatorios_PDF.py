# --- bootstrap de caminho ---
from pathlib import Path
import sys
_THIS = Path(__file__).resolve()
_ROOT = None
for p in _THIS.parents:
    if (p / "app").exists():
        _ROOT = p
        break
if _ROOT and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
# --- fim bootstrap ---

import json
from pathlib import Path as _P
import streamlit as st
import pandas as pd

from app.ui.utils import (
    DATA_DIR, list_transaction_files, load_df, load_threshold, render_header
)

st.set_page_config(page_title="Relatórios (PDF)", layout="wide")
render_header(st, "Relatórios (PDF)", "Gera PDF com o recorte desejado")

files = list_transaction_files()
if not files:
    st.info("Nenhum CSV. Gere dados na Home.")
    st.stop()

sel = st.selectbox("Arquivo", options=files, index=len(files)-1, format_func=lambda p: p.name)
df = load_df(sel)
thr = load_threshold()

opt = st.selectbox(
    "Escolha o conjunto",
    ["Críticos (score < limiar)", "Todos", "Suspeitos (score < 70)", "Abaixo de 50", "Personalizado"],
    index=0
)
custom_lim = 60
if opt == "Personalizado":
    custom_lim = st.slider("Score abaixo de", 0, 100, 60)

def filter_df(df_in: pd.DataFrame) -> pd.DataFrame:
    if opt == "Críticos (score < limiar)":
        return df_in[df_in["score"] < thr]
    if opt == "Todos":
        return df_in
    if opt == "Suspeitos (score < 70)":
        return df_in[df_in["score"] < 70]
    if opt == "Abaixo de 50":
        return df_in[df_in["score"] < 50]
    return df_in[df_in["score"] < custom_lim]

fdf = filter_df(df)
st.metric("Registros para PDF", len(fdf))

col1, col2 = st.columns([1,2])
with col1:
    if st.button("Gerar PDF agora", type="primary"):
        import gerar_relatorio as gr
        path = gr.build_pdf(rows=fdf.to_dict(orient="records"), threshold=thr)
        st.session_state._pdf_path = str(path)
        st.success(f"Gerado: {_P(path).name}")

with col2:
    p = st.session_state.get("_pdf_path")
    if p and _P(p).exists():
        with open(p, "rb") as f:
            st.download_button("Baixar PDF", data=f.read(), file_name=_P(p).name, mime="application/pdf")
    else:
        st.info("Nenhum PDF gerado nesta sessão.")
