import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]   # 'app' -> sobe 1 nível = raiz do projeto
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sys, subprocess, os
import streamlit as st
from app.ui.utils import ROOT, DATA_DIR, render_header, safe_rerun

st.set_page_config(page_title="Dashboard (Home)", layout="wide")
render_header("Dashboard (Home)", f"Diretório de dados: {DATA_DIR}")

c1, c2 = st.columns([2,1])

with c1:
    if st.button("⚡ Coletar agora (ETH)", type="primary", use_container_width=True):
        try:
            cmd = [sys.executable, "main.py", "-c", "eth"]
            out = subprocess.run(
                cmd, cwd=str(ROOT), capture_output=True, text=True, check=True
            )
            st.success("Coleta executada com sucesso.")
            with st.expander("Log da coleta"):
                st.code(out.stdout or "(sem saída)")
            safe_rerun()
        except subprocess.CalledProcessError as e:
            st.error("Erro inesperado na coleta.")
            with st.expander("Trace / log do erro"):
                st.code((e.stdout or "") + "\n" + (e.stderr or ""))

with c2:
    if st.button("🗑️  Limpar dados (CSV)", use_container_width=True):
        try:
            for p in DATA_DIR.glob("transactions*.csv"):
                p.unlink(missing_ok=True)
            (DATA_DIR / "pending_review.csv").unlink(missing_ok=True)
            (DATA_DIR / "transactions.csv").unlink(missing_ok=True)
            st.success("CSV(s) removidos.")
            safe_rerun()
        except Exception as e:
            st.error(f"Falha ao excluir arquivos: {e}")
