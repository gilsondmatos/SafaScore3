# --- bootstrap de caminho para permitir "from app...." ---
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
# --- fim do bootstrap ---

import streamlit as st
import pandas as pd

from app.ui.utils import (
    DATA_DIR, list_transaction_files, load_df, load_threshold,
    render_header, run_collect_eth, clear_transactions
)

st.set_page_config(page_title="SafeScore • Home", layout="wide")

# Flags para ações assíncronas “seguras”
if "do_collect" not in st.session_state:
    st.session_state.do_collect = False
if "do_clear" not in st.session_state:
    st.session_state.do_clear = False

render_header(st, "SafeScore — Plataforma Antifraude", f"Diretório de dados: {DATA_DIR}")

colA, colB = st.columns([2, 1])
with colA:
    if st.button("⚡ Coletar agora (ETH)", type="primary", use_container_width=True):
        st.session_state.do_collect = True
        st.rerun()
with colB:
    if st.button("🧹 Limpar dados (teste)", help="Apaga transactions*.csv e zera pending_review.csv"):
        st.session_state.do_clear = True
        st.rerun()

# ciclo 2: efetiva ações
if st.session_state.do_collect:
    ok, log = run_collect_eth()
    st.session_state.do_collect = False
    if ok:
        st.success("Coleta executada com sucesso. Recarregando páginas…")
    else:
        st.error("Falha na coleta. Veja o log abaixo.")
    with st.expander("Log da coleta", expanded=True):
        st.code(log, language="bash")
    st.rerun()

if st.session_state.do_clear:
    deleted, zreset = clear_transactions()
    st.session_state.do_clear = False
    st.info(f"Removidos {deleted} arquivo(s) de transação e zerado pending_review: {bool(zreset)}.")
    st.rerun()

# Mini-dashboard na Home
files = list_transaction_files()
if not files:
    st.info("Nenhum CSV encontrado em app/data. Clique em **Coletar agora (ETH)** para gerar dados.")
    st.stop()

sel = st.selectbox("Arquivo de transações", options=files, index=len(files) - 1, format_func=lambda p: p.name)
df = load_df(sel)
thr = load_threshold()

c1, c2, c3 = st.columns(3)
c1.metric("Transações (arquivo)", len(df))
c2.metric("Média de score", round(df["score"].mean(), 1) if not df.empty else 0)
c3.metric("Críticas (< limiar)", int((df["score"] < thr).sum()) if not df.empty else 0)

st.subheader("Transações (amostra)")
cols_show = [c for c in ["tx_id","timestamp","from_address","to_address","amount","token","method","chain","score","penalty_total"] if c in df.columns]
st.dataframe(df[cols_show].sort_values(by="timestamp", ascending=False).head(20), use_container_width=True, height=360)
