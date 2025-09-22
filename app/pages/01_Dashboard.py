import pandas as pd, altair as alt, streamlit as st
from pathlib import Path
# --- bootstrap do PYTHONPATH (coloque no topo do arquivo) ---
import sys
# ------------------------------------------------------------
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]   # 'app' -> sobe 1 nível = raiz do projeto
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.ui.utils import (
    DATA_DIR, list_transaction_files, load_df, load_threshold,
    parse_contrib_dict, render_header
)

st.set_page_config(page_title="Dashboard", layout="wide")
render_header("Dashboard", f"KPIs e gráficos  |  Dados: {DATA_DIR}")

files = list_transaction_files()
if not files:
    st.info("Nenhum CSV em app/data. Vá em **Home → Coletar agora (ETH)**.")
    st.stop()

sel = st.selectbox("Arquivo", options=files, index=len(files)-1, format_func=lambda p: p.name)
df = load_df(Path(sel))
if df.empty:
    st.warning("Arquivo selecionado está vazio.")
    st.stop()

thr = load_threshold(50)
total = len(df)
avg = round(df["score"].mean(), 1) if "score" in df.columns and total else 0
crit = int((df["score"] < thr).sum()) if "score" in df.columns else 0

c1,c2,c3 = st.columns(3)
c1.metric("Transações", total)
c2.metric("Média de score", avg)
c3.metric("Críticas (< limiar)", crit)

st.divider()

def has_col(c): return c in df.columns and not df[c].isna().all()

g1,g2 = st.columns(2)
with g1:
    if has_col("token"):
        st.altair_chart(
            alt.Chart(df).mark_bar().encode(x="token:N", y="count():Q").properties(height=300, title="Por token"),
            use_container_width=True
        )
with g2:
    if has_col("method"):
        st.altair_chart(
            alt.Chart(df).mark_bar().encode(x="method:N", y="count():Q").properties(height=300, title="Por método"),
            use_container_width=True
        )

if has_col("timestamp"):
    tmp = df.copy()
    tmp["hour"] = pd.to_datetime(tmp["timestamp"], errors="coerce").dt.hour
    tmp = tmp.dropna(subset=["hour"])
    if not tmp.empty:
        st.altair_chart(
            alt.Chart(tmp).mark_bar().encode(x="hour:O", y="count():Q").properties(height=300, title="Por hora do dia"),
            use_container_width=True
        )

st.divider()

if "explain" in df.columns:
    rows = []
    for row in df.itertuples(index=False):
        contrib = parse_contrib_dict(getattr(row, "explain", ""))
        for k, v in (contrib or {}).items():
            rows.append({"rule": k, "pct": v})
    cx = pd.DataFrame(rows)
    if not cx.empty:
        top = cx.groupby("rule")["pct"].mean().sort_values(ascending=False).head(10).reset_index()
        st.altair_chart(
            alt.Chart(top).mark_bar().encode(x="rule:N", y="pct:Q").properties(height=320, title="Top regras por contribuição média (%)"),
            use_container_width=True
        )
