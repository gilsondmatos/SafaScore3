from __future__ import annotations
import pandas as pd
import streamlit as st

from app.ui.utils import (
    DATA_DIR,
    render_header,
    load_list_df,
    save_list_df,
    download_button_for_list,
)

# Cabeçalho
render_header("Listas e Regras", "Edite listas e configure pesos sem sair do app")

st.caption(f"Diretório de dados: `{DATA_DIR}`")

# ----------------- Editor de listas -----------------
st.subheader("Listas (CSV)")

def list_block(kind: str, title: str):
    df, path, cols = load_list_df(kind)
    st.markdown(f"**{title}** — `{path}`")
    with st.form(f"form_{kind}", clear_on_submit=False):
        edited = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            height=260,
            key=f"editor_{kind}",
        )
        ok = st.form_submit_button("Salvar alterações", type="primary")
        if ok:
            save_list_df(kind, edited)
            st.success(f"{title}: salvo em {path.name}")

    # download deve ficar **fora** do form
    download_button_for_list(kind)

cols_top = st.columns(2)
with cols_top[0]:
    list_block("blacklist", "blacklist.csv")
with cols_top[1]:
    list_block("watchlist", "watchlist.csv")

cols_mid = st.columns(2)
with cols_mid[0]:
    list_block("sensitive_tokens", "sensitive_tokens.csv")
with cols_mid[1]:
    list_block("sensitive_methods", "sensitive_methods.csv")

st.divider()
list_block("known_addresses", "known_addresses.csv")

# ----------------- Pesos (somente leitura aqui) -----------------
st.divider()
st.subheader("Pesos (regras) atuais")

try:
    from app.engine.scoring import DEFAULT_WEIGHTS  # leitura apenas
    st.caption("Os pesos default residem em `app/engine/scoring.py` → `DEFAULT_WEIGHTS`.")
    st.json(DEFAULT_WEIGHTS)
except Exception:
    st.info("Não foi possível ler DEFAULT_WEIGHTS de app/engine/scoring.py.")
