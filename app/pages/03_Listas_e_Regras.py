# app/pages/03_Listas_e_Regras.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

# --------------------------------------------------------------------
# Imports utilitários existentes no projeto (não altere utils.py)
# --------------------------------------------------------------------
from app.ui.utils import (
    ROOT, DATA_DIR, render_header,
    load_blacklist, load_watchlist,
    load_sensitive_tokens, load_sensitive_methods,
    save_csv_table, download_bytes_button,
    success_alert, error_alert,
)

st.set_page_config(page_title="Listas e Regras", layout="wide")
render_header(st, "Listas e Regras", "Edite listas e configure pesos sem sair do app")

# ====================================================================
# 1) Editor genérico de CSV (edição inline)
# ====================================================================
def _csv_editor_block(
    title: str,
    path: Path,
    loader_func,
    expected_cols: List[str],
    key_prefix: str
):
    st.subheader(title)
    st.caption("Adicione/edite/exclua diretamente na tabela. Clique em **Salvar alterações** para persistir.")

    df: pd.DataFrame = loader_func()
    edited = st.data_editor(
        df,
        key=f"ed_{key_prefix}",
        num_rows="dynamic",
        use_container_width=True,
        height=250,
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("💾 Salvar alterações", key=f"save_{key_prefix}", use_container_width=True):
            ok, msg = save_csv_table(path, edited, expected_cols)
            (success_alert if ok else error_alert)(msg)

    with c2:
        csv_bytes = edited.to_csv(index=False).encode("utf-8")
        download_bytes_button(
            f"⬇️ Baixar CSV ({path.name})",
            path.name,
            csv_bytes
        )

    st.divider()


# ------------------ BLACKLIST ------------------
_csv_editor_block(
    title="blacklist",
    path=DATA_DIR / "blacklist.csv",
    loader_func=load_blacklist,
    expected_cols=["address", "reason"],
    key_prefix="blacklist",
)

# ------------------ WATCHLIST ------------------
_csv_editor_block(
    title="watchlist",
    path=DATA_DIR / "watchlist.csv",
    loader_func=load_watchlist,
    expected_cols=["address", "note"],
    key_prefix="watchlist",
)

# ------------------ SENSITIVE TOKENS & METHODS ------------------
c1, c2 = st.columns(2, gap="large")

with c1:
    _csv_editor_block(
        title="sensitive_tokens",
        path=DATA_DIR / "sensitive_tokens.csv",
        loader_func=load_sensitive_tokens,
        expected_cols=["token"],
        key_prefix="sensitive_tokens",
    )

with c2:
    _csv_editor_block(
        title="sensitive_methods",
        path=DATA_DIR / "sensitive_methods.csv",
        loader_func=load_sensitive_methods,
        expected_cols=["method"],
        key_prefix="sensitive_methods",
    )

# ====================================================================
# 2) Pesos (regras) – UI compacta com legenda + input + “＋”
# ====================================================================
st.subheader("Pesos (regras) atuais")
st.caption("Ajuste pelos campos numéricos ou pelo botão **＋**. Clique em **Salvar pesos**.")

# Pesos padrão (iguais ao motor de score)
DEFAULT_WEIGHTS: Dict[str, int] = {
    "blacklist": 60,
    "watchlist": 30,
    "high_amount": 25,
    "unusual_hour": 15,
    "new_address": 40,
    "velocity": 20,
    "sensitive_token": 15,
    "sensitive_method": 20,
}
ORDER = [
    "blacklist",
    "watchlist",
    "high_amount",
    "unusual_hour",
    "new_address",
    "velocity",
    "sensitive_token",
    "sensitive_method",
]
RULE_HELP = {
    "blacklist":        "Endereço presente na blacklist da empresa (alerta forte).",
    "watchlist":        "Endereço monitorado/sob observação (alerta moderado).",
    "high_amount":      "Valor alto de transação em moeda/token monitorado.",
    "unusual_hour":     "Transação em horário incomum para o padrão da operação.",
    "new_address":      "Remetente novo (ainda não visto na base).",
    "velocity":         "Muitas transações em janela curta (pico de atividade).",
    "sensitive_token":  "Tokens sensíveis (ex.: USDT, USDC, DAI, WBTC, WETH…).",
    "sensitive_method": "Métodos sensíveis (ex.: approve, transferFrom, permit…).",
}

# Carregar overrides salvos
weights_path = DATA_DIR / "weights.json"
if weights_path.exists():
    try:
        DEFAULT_WEIGHTS.update(json.loads(weights_path.read_text(encoding="utf-8")))
    except Exception:
        pass

# Iniciar estado (para botões +)
for k in ORDER:
    st.session_state.setdefault(f"w_{k}", int(DEFAULT_WEIGHTS.get(k, 0)))

# CSS leve para inputs menores
st.markdown(
    """
    <style>
      /* compactar linhas e inputs */
      .weights-row { padding: 6px 8px; border-radius: 10px; }
      .weights-row:hover { background: rgba(255,255,255,0.03); }
      .weights-title { margin-bottom: 4px !important; }
      .weights-help { color: #9aa0a6; font-size: 0.9rem; margin-top: -3px; }
      .weights-input > div > input { text-align: right; }
    </style>
    """,
    unsafe_allow_html=True
)

# recomendações padrão
DEFAULT_WEIGHTS: Dict[str, int] = {
    "blacklist": 59,
    "watchlist": 30,
    "high_amount": 25,
    "unusual_hour": 14,
    "new_address": 40,
    "velocity": 20,
    "sensitive_token": 15,
    "sensitive_method": 20,
}

# legendas curtas (UX)
RULE_DESCR = {
    "blacklist": "Endereço presente na blacklist da empresa (alerta forte).",
    "watchlist": "Endereço monitorado/sob observação (alerta moderado).",
    "high_amount": "Valor alto de transação em moeda/token monitorado.",
    "unusual_hour": "Transação em horário incomum para o padrão da operação.",
    "new_address": "Remetente novo (endereço ainda não visto na base).",
    "velocity": "Muitas transações em janela de tempo curta (pico de atividade).",
    "sensitive_token": "Tokens sensíveis (ex.: USDT, USDC, DAI, WBTC, WETH…).",
    "sensitive_method": "Métodos sensíveis (ex.: approve, transferFrom, permit…).",
}

weights_path = DATA_DIR / "weights.json"
weights: Dict[str, int] = DEFAULT_WEIGHTS.copy()

# carrega salvo, se existir
if weights_path.exists():
    try:
        loaded = json.loads(weights_path.read_text(encoding="utf-8"))
        for k, v in loaded.items():
            if k in weights and isinstance(v, (int, float)):
                weights[k] = int(v)
    except Exception:
        pass

# ordem fixa para consistência visual
ORDER = [
    "blacklist",
    "watchlist",
    "high_amount",
    "unusual_hour",
    "new_address",
    "velocity",
    "sensitive_token",
    "sensitive_method",
]

# toolbar: restaurar padrão
tcol1, tcol2 = st.columns([6,1])
with tcol2:
    if st.button("↺ Restaurar padrão", use_container_width=True):
        weights = DEFAULT_WEIGHTS.copy()
        st.success("Pesos restaurados para os valores recomendados.")

# formulário compacto
with st.form("weights_form"):
    for key in ORDER:
        left, right = st.columns([3.5, 1.2], vertical_alignment="center")
        with left:
            st.markdown(f"<div class='weights-row'>"
                        f"<div class='weights-title'><strong>{key.replace('_',' ')}</strong></div>"
                        f"<div class='weights-help'>{RULE_DESCR.get(key,'')}</div>"
                        f"</div>", unsafe_allow_html=True)
        with right:
            weights[key] = st.number_input(
                label="",
                key=f"w_{key}",
                min_value=0,
                max_value=100,
                step=1,
                value=int(weights[key]),
                help=f"Peso da regra '{key}'.",
                format="%d",
            )

    saved = st.form_submit_button("💾 Salvar pesos", use_container_width=True)
    if saved:
        try:
            weights_path.write_text(json.dumps(weights, ensure_ascii=False, indent=2), encoding="utf-8")
            st.success("Pesos salvos com sucesso.")
        except Exception as e:
            st.error(f"Falha ao salvar pesos: {e}")