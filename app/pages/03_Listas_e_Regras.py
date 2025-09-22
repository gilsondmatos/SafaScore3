# app/pages/03_Listas_e_Regras.py
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

# Garante import relativo
THIS = Path(__file__).resolve()
ROOT = THIS.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui.utils import (  # noqa: E402
    DATA_DIR, inject_css, render_header,
    read_csv, write_csv, df_to_editor,
    load_weights, save_weights
)

st.set_page_config(page_title="Listas e Regras — SafeScore", layout="wide")
inject_css()
render_header("Listas e Regras", "Edite listas e configure pesos sem sair do app")

# Caminhos
BLACKLIST = DATA_DIR / "blacklist.csv"
WATCHLIST = DATA_DIR / "watchlist.csv"
SENS_TOK = DATA_DIR / "sensitive_tokens.csv"
SENS_MET = DATA_DIR / "sensitive_methods.csv"

# -----------------------------------
# Seção: Blacklist
# -----------------------------------
st.markdown("### blacklist.csv")
with st.container():
    st.caption("Itens atuais (adicione/edite/exclua diretamente na tabela).")
    df_bl = read_csv(BLACKLIST, ["address", "reason"])
    ed_bl = df_to_editor(df_bl, key="ed_blacklist")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("💾 Salvar alterações (blacklist.csv)", use_container_width=True):
            # Limpa linhas vazias
            ed_bl = ed_bl.fillna("").replace({"address": r"^\s*$"}, {"address": ""}, regex=True)
            ed_bl = ed_bl[ed_bl["address"].astype(str).str.strip() != ""]
            write_csv(BLACKLIST, ed_bl, ["address", "reason"])
            st.success("Blacklist salva.")
    with c2:
        st.download_button(
            "⬇️ Baixar CSV (blacklist.csv)",
            data=ed_bl.to_csv(index=False).encode("utf-8"),
            file_name="blacklist.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.markdown("---")

# -----------------------------------
# Seção: Watchlist
# -----------------------------------
st.markdown("### watchlist.csv")
with st.container():
    st.caption("Itens atuais (adicione/edite/exclua diretamente na tabela).")
    df_wl = read_csv(WATCHLIST, ["address", "note"])
    ed_wl = df_to_editor(df_wl, key="ed_watchlist")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("💾 Salvar alterações (watchlist.csv)", use_container_width=True):
            ed_wl = ed_wl.fillna("").replace({"address": r"^\s*$"}, {"address": ""}, regex=True)
            ed_wl = ed_wl[ed_wl["address"].astype(str).str.strip() != ""]
            write_csv(WATCHLIST, ed_wl, ["address", "note"])
            st.success("Watchlist salva.")
    with c2:
        st.download_button(
            "⬇️ Baixar CSV (watchlist.csv)",
            data=ed_wl.to_csv(index=False).encode("utf-8"),
            file_name="watchlist.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.markdown("---")

# -----------------------------------
# Seção: Tokens e Methods sensíveis (lado a lado)
# -----------------------------------
left, right = st.columns(2, gap="large")

with left:
    st.markdown("### sensitive_tokens.csv")
    st.caption("Tokens atuais (adicione/edite/exclua diretamente na tabela).")
    df_tok = read_csv(SENS_TOK, ["token"])
    ed_tok = df_to_editor(df_tok, key="ed_tokens")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("💾 Salvar alterações", use_container_width=True):
            ed_tok = ed_tok.fillna("").replace({"token": r"^\s*$"}, {"token": ""}, regex=True)
            ed_tok = ed_tok[ed_tok["token"].astype(str).str.strip() != ""]
            write_csv(SENS_TOK, ed_tok, ["token"])
            st.success("Lista de tokens salva.")
    with c2:
        st.download_button(
            "⬇️ Baixar CSV (sensitive_tokens.csv)",
            data=ed_tok.to_csv(index=False).encode("utf-8"),
            file_name="sensitive_tokens.csv",
            mime="text/csv",
            use_container_width=True,
        )

with right:
    st.markdown("### sensitive_methods.csv")
    st.caption("Methods atuais (adicione/edite/exclua diretamente na tabela).")
    df_met = read_csv(SENS_MET, ["method"])
    ed_met = df_to_editor(df_met, key="ed_methods")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("💾 Salvar alterações (sensitive_methods.csv)", use_container_width=True):
            ed_met = ed_met.fillna("").replace({"method": r"^\s*$"}, {"method": ""}, regex=True)
            ed_met = ed_met[ed_met["method"].astype(str).str.strip() != ""]
            write_csv(SENS_MET, ed_met, ["method"])
            st.success("Lista de methods salva.")
    with c2:
        st.download_button(
            "⬇️ Baixar CSV (sensitive_methods.csv)",
            data=ed_met.to_csv(index=False).encode("utf-8"),
            file_name="sensitive_methods.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.markdown("---")

# -----------------------------------
# Seção: Pesos (regras)
# -----------------------------------
st.markdown("### Pesos (regras) atuais")
st.caption("Ajuste nos campos e clique em **Salvar pesos**. Os valores abaixo já vêm dos padrões recomendados.")

weights = load_weights()  # <-- carrega defaults (se não existir JSON)
rules = list(weights.keys())

# Layout em duas colunas para ficar mais respirado
col_a, col_b = st.columns(2, gap="large")
half = (len(rules) + 1) // 2

with col_a:
    st.subheader("Regras", divider="orange")
    for rule in rules[:half]:
        val = st.number_input(
            rule,
            min_value=0, max_value=100,
            step=1,
            value=int(weights.get(rule, 0)),
            key=f"w_{rule}",
        )
        weights[rule] = int(val)

with col_b:
    st.subheader(" ", divider="orange")
    for rule in rules[half:]:
        val = st.number_input(
            rule,
            min_value=0, max_value=100,
            step=1,
            value=int(weights.get(rule, 0)),
            key=f"w_{rule}",
        )
        weights[rule] = int(val)

st.markdown("")
c1, c2 = st.columns([1, 3])
with c1:
    if st.button("💾 Salvar pesos", use_container_width=True):
        save_weights(weights)
        st.success("Pesos salvos em app/data/weights.json. O motor de score passará a usar esses valores.")
with c2:
    st.json(weights, expanded=False)
