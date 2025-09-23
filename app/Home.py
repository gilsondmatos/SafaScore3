import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st
st.caption(f"requests: {requests.__version__}")

from app.ui.utils import (
    ROOT, DATA_DIR, list_transaction_files, load_df,
    render_header, success_alert, error_alert, info_alert
)

st.set_page_config(page_title="Dashboard (Home)", layout="wide")

render_header(
    st,
    "Dashboard (Home)",
    f"Diretório de dados: {DATA_DIR}"
)

# ------------------------------------------------------------------
# Ações (coletar e limpar)
# ------------------------------------------------------------------
c1, c2 = st.columns([2, 1])

with c1:
    if st.button("⚡ Coletar agora (ETH)", use_container_width=True):
        with st.status("Executando coleta on-chain (ETH)...", expanded=True) as status:
            try:
                # Executa main.py com o coletor ETH
                # Obs.: Usa o Python do mesmo ambiente
                cmd = ["python", str(ROOT / "main.py"), "-c", "eth"]
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, cwd=str(ROOT), timeout=180
                )
                st.write(proc.stdout or "")
                if proc.returncode != 0:
                    st.write(proc.stderr or "")
                    status.update(label="Coleta finalizada com erros.", state="error")
                    error_alert("Falha na coleta. Veja o log acima.")
                else:
                    status.update(label="Coleta finalizada.", state="complete")
                    success_alert("Coleta concluída com sucesso.")
            except Exception as e:
                status.update(label="Erro inesperado na coleta.", state="error")
                error_alert(f"Erro inesperado: {e}")

with c2:
    if st.button("🗑️ Limpar dados (CSV)", use_container_width=True):
        apagados = 0
        for p in list(DATA_DIR.glob("transactions*.csv")) + [
            DATA_DIR / "pending_review.csv"
        ]:
            if p.exists():
                try:
                    p.unlink()
                    apagados += 1
                except Exception:
                    pass
        success_alert(f"Arquivos removidos: {apagados}.")

st.divider()

# ------------------------------------------------------------------
# Tabela com as transações mais recentes
# ------------------------------------------------------------------
files = list_transaction_files()
if not files:
    info_alert("Nenhum arquivo de transações encontrado. Clique em **Coletar agora (ETH)**.")
else:
    latest = files[-1]
    st.subheader(f"Transações recentes — `{latest.name}`")
    df: pd.DataFrame = load_df(latest)
    if df.empty:
        st.warning("Arquivo vazio.")
    else:
        # Ordena (mais novo primeiro) se houver timestamp
        if "timestamp" in df.columns and df["timestamp"].notna().any():
            df = df.sort_values(by="timestamp", ascending=False)
        # Colunas mais relevantes primeiro
        cols_show = [
            "timestamp", "tx_id", "from_address", "to_address",
            "amount", "token", "method", "chain", "score", "reasons"
        ]
        cols_show = [c for c in cols_show if c in df.columns]
        st.dataframe(
            df[cols_show],
            height=520,
            use_container_width=True
        )
