import pandas as pd, streamlit as st
from pathlib import Path
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]   # 'app' -> sobe 1 nível = raiz do projeto
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.ui.utils import list_transaction_files, load_df, render_header

st.set_page_config(page_title="Triage e Export", layout="wide")
render_header("Triage e Export", "Filtros e exportação")

files = list_transaction_files()
if not files:
    st.info("Nenhum CSV encontrado.")
    st.stop()

sel = st.selectbox("Arquivo", options=files, index=len(files)-1, format_func=lambda p: p.name)
df = load_df(Path(sel))
if df.empty:
    st.warning("Arquivo vazio.")
    st.stop()

c = st.columns(4)
txt = c[0].text_input("Endereço contém", "")
tok = c[1].selectbox("Token", ["(todos)"] + (sorted(df["token"].dropna().unique().tolist()) if "token" in df.columns else []))
mt  = c[2].selectbox("Método", ["(todos)"] + (sorted(df["method"].dropna().unique().tolist()) if "method" in df.columns else []))
min_score = c[3].number_input("Score mínimo", 0, 100, 0)

flt = df.copy()
if txt.strip():
    mask = False
    for col in ["from_address","to_address"]:
        if col in flt.columns:
            mask = mask | flt[col].fillna("").str.contains(txt, case=False)
    flt = flt[mask]
if tok!="(todos)" and "token" in flt.columns:
    flt = flt[flt["token"]==tok]
if mt!="(todos)" and "method" in flt.columns:
    flt = flt[flt["method"]==mt]
if "score" in flt.columns:
    flt = flt[flt["score"]>=int(min_score)]

st.caption(f"Mostrando {len(flt)} de {len(df)} linhas.")
st.dataframe(flt, use_container_width=True, height=460)
st.download_button("Baixar CSV filtrado", flt.to_csv(index=False).encode("utf-8"),
                   file_name=f"triage_{Path(sel).stem}.csv", mime="text/csv")
