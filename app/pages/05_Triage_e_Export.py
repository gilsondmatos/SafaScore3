# app/pages/05_Triage_e_Export.py
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# --- bootstrap para resolver "No module named 'app'"
ROOT = Path(__file__).resolve().parents[1]  # 'app' -> sobe 1 nível (raiz do projeto)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui.utils import (
    list_transaction_files,
    load_df,
    render_header,  # assinatura: render_header(st_mod, title, subtitle=None)
)

# -----------------------------------------------------------------------------
# Página
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Triage e Export", layout="wide")
render_header(st, "Triage e Export", "Filtros e exportação")

# Arquivos disponíveis
files = list_transaction_files()
if not files:
    st.info("Nenhum CSV encontrado em app/data. Gere via Home → Coletar agora (ETH).")
    st.stop()

# Seleção de arquivo (default = o mais recente)
sel = st.selectbox(
    "Arquivo",
    options=files,
    index=len(files) - 1,
    format_func=lambda p: p.name,
)

# Carrega dataframe
df = load_df(Path(sel))
if df.empty:
    st.warning("Arquivo selecionado está vazio.")
    st.stop()

# -----------------------------------------------------------------------------
# Filtros
# -----------------------------------------------------------------------------
# Opções defensivas (se a coluna não existir, lista fica vazia)
token_opts = ["(todos)"]
if "token" in df.columns:
    token_opts += sorted([t for t in df["token"].dropna().unique().tolist() if str(t).strip()])

method_opts = ["(todos)"]
if "method" in df.columns:
    method_opts += sorted([m for m in df["method"].dropna().unique().tolist() if str(m).strip()])

c1, c2, c3, c4, c5 = st.columns([2, 1.2, 1.2, 1.2, 0.8])
addr_txt = c1.text_input("Endereço contém", "")
tok_sel = c2.selectbox("Token", token_opts)
met_sel = c3.selectbox("Método", method_opts)
min_score = c4.number_input("Score mínimo", min_value=0, max_value=100, value=0, step=1)
do_reset = c5.button("Limpar filtros")

if do_reset:
    # força recarregar com valores padrão
    st.rerun()

# -----------------------------------------------------------------------------
# Aplica filtros
# -----------------------------------------------------------------------------
flt = df.copy()

# Texto em endereço (from/to)
if addr_txt.strip():
    mask = False
    for col in ("from_address", "to_address"):
        if col in flt.columns:
            col_mask = flt[col].fillna("").str.contains(addr_txt, case=False, na=False)
            mask = col_mask if mask is False else (mask | col_mask)
    if mask is not False:
        flt = flt[mask]

# Token
if tok_sel != "(todos)" and "token" in flt.columns:
    flt = flt[flt["token"] == tok_sel]

# Método
if met_sel != "(todos)" and "method" in flt.columns:
    flt = flt[flt["method"] == met_sel]

# Score mínimo
if "score" in flt.columns:
    flt = flt[pd.to_numeric(flt["score"], errors="coerce").fillna(0) >= int(min_score)]

# -----------------------------------------------------------------------------
# KPIs + Tabela + Export
# -----------------------------------------------------------------------------
k1, k2, k3 = st.columns(3)
k1.metric("Linhas filtradas", len(flt))
k2.metric("Total no arquivo", len(df))
if "score" in flt.columns and not flt.empty:
    k3.metric("Score médio (filtro)", round(pd.to_numeric(flt["score"], errors="coerce").mean(), 1))
else:
    k3.metric("Score médio (filtro)", "-")

st.dataframe(flt, use_container_width=True, height=460)

st.download_button(
    "Baixar CSV filtrado",
    data=flt.to_csv(index=False).encode("utf-8"),
    file_name=f"triage_{Path(sel).stem}.csv",
    mime="text/csv",
    use_container_width=True,
)
