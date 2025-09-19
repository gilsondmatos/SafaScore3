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
import streamlit as st

from app.ui.utils import DATA_DIR, list_transaction_files, load_df, load_threshold, render_header

st.set_page_config(page_title="Triage & Export", layout="wide")
render_header(st, "Triage & Export", "Filtre e exporte JSONL/CSV")

files = list_transaction_files()
if not files:
    st.info("Nenhum CSV. Gere dados na Home.")
    st.stop()

sel = st.selectbox("Arquivo", options=files, index=len(files)-1, format_func=lambda p: p.name)
df = load_df(sel)
thr = load_threshold()

opt = st.selectbox("Filtro", ["Críticos (< limiar)","Todos","Suspeitos (<70)","<50","Personalizado"], index=0)
lim = 60
if opt == "Personalizado":
    lim = st.slider("Score abaixo de", 0, 100, 60)

def apply(df):
    if opt == "Críticos (< limiar)":
        return df[df["score"] < thr]
    if opt == "Todos":
        return df
    if opt == "Suspeitos (<70)":
        return df[df["score"] < 70]
    if opt == "<50":
        return df[df["score"] < 50]
    return df[df["score"] < lim]

fdf = apply(df)
st.metric("Registros", len(fdf))
st.dataframe(fdf.head(50), use_container_width=True, height=300)

col1, col2 = st.columns([1,1])
with col1:
    j = "\n".join(json.dumps(r, ensure_ascii=False) for r in fdf.to_dict(orient="records"))
    st.download_button("Baixar JSONL", data=j.encode("utf-8"), file_name=f"{sel.stem}_filtro.jsonl", mime="application/json")
with col2:
    st.download_button("Baixar CSV", data=fdf.to_csv(index=False).encode("utf-8"), file_name=f"{sel.stem}_filtro.csv", mime="text/csv")
