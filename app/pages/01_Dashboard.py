# 01_Dashboard.py  — KPIs e gráficos

# --- bootstrap para resolver "No module named 'app'" em execuções como `streamlit run app/xxx.py`
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()
# Sobe até achar o diretório do projeto (aquele que contém a pasta "app")
for parent in _THIS.parents:
    if (parent / "app").is_dir():
        _PROJ = parent
        break
else:
    _PROJ = _THIS.parent  # fallback mínimo

if str(_PROJ) not in sys.path:
    sys.path.insert(0, str(_PROJ))
# --------------------------------------------------------------------

import pandas as pd
import altair as alt
import streamlit as st

from app.ui.utils import (
    DATA_DIR,
    list_transaction_files,
    load_df,
    load_threshold,
    parse_contrib_dict,
    render_header,
)

# --------------------------------------------------------------------
st.set_page_config(page_title="Dashboard", layout="wide")
# >>> passa o módulo `st` como 1º arg:
render_header(st, "Dashboard", f"KPIs e gráficos  |  Dados: {DATA_DIR}")

# --------------------------------------------------------------------
# Arquivo selecionado
files = list_transaction_files()
if not files:
    st.info("Nenhum CSV em app/data. Vá em **Home → Coletar agora (ETH)** para gerar dados.")
    st.stop()

sel = st.selectbox(
    "Arquivo",
    options=files,
    index=len(files) - 1,
    format_func=lambda p: getattr(p, "name", str(p)),
)

df = load_df(Path(sel))
if df.empty:
    st.warning("Arquivo selecionado está vazio.")
    st.stop()

# --------------------------------------------------------------------
# KPIs
thr = load_threshold(50)
total = len(df)
avg = round(df["score"].mean(), 1) if "score" in df.columns and total else 0
crit = int((df["score"] < thr).sum()) if "score" in df.columns else 0

c1, c2, c3 = st.columns(3)
c1.metric("Transações", total)
c2.metric("Média de score", avg)
c3.metric("Críticas (< limiar)", crit)

st.divider()

# --------------------------------------------------------------------
def _has_col(col: str) -> bool:
    return col in df.columns and not df[col].isna().all()

# Gráficos categoriais
g1, g2 = st.columns(2)
with g1:
    if _has_col("token"):
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(x=alt.X("token:N", title="Token"), y=alt.Y("count():Q", title="Contagem"))
            .properties(height=300, title="Transações por token")
        )
        st.altair_chart(chart, use_container_width=True)

with g2:
    if _has_col("method"):
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(x=alt.X("method:N", title="Método"), y=alt.Y("count():Q", title="Contagem"))
            .properties(height=300, title="Transações por método")
        )
        st.altair_chart(chart, use_container_width=True)

# Histograma por hora
if _has_col("timestamp"):
    tmp = df.copy()
    tmp["hour"] = pd.to_datetime(tmp["timestamp"], errors="coerce").dt.hour
    tmp = tmp.dropna(subset=["hour"])
    if not tmp.empty:
        chart = (
            alt.Chart(tmp)
            .mark_bar()
            .encode(x=alt.X("hour:O", title="Hora do dia"), y=alt.Y("count():Q", title="Contagem"))
            .properties(height=300, title="Transações por hora do dia")
        )
        st.altair_chart(chart, use_container_width=True)

st.divider()

# --------------------------------------------------------------------
# Contribuição média de regras (quando existir a coluna "explain")
if "explain" in df.columns:
    rows = []
    for row in df.itertuples(index=False):
        contrib = parse_contrib_dict(getattr(row, "explain", ""))
        for k, v in (contrib or {}).items():
            rows.append({"rule": k, "pct": v})
    cx = pd.DataFrame(rows)
    if not cx.empty:
        top = (
            cx.groupby("rule", as_index=False)["pct"]
            .mean()
            .sort_values("pct", ascending=False)
            .head(10)
        )
        chart = (
            alt.Chart(top)
            .mark_bar()
            .encode(x=alt.X("rule:N", title="Regra"), y=alt.Y("pct:Q", title="Contribuição média (%)"))
            .properties(height=320, title="Top regras por contribuição média (%)")
        )
        st.altair_chart(chart, use_container_width=True)
