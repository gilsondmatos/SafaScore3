# app/ui/utils.py
from __future__ import annotations
from pathlib import Path
import json
import os
import pandas as pd
import streamlit as st

# Raízes e diretórios
ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT / "app" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Arquivo de pesos persistidos
WEIGHTS_PATH: Path = DATA_DIR / "weights.json"

# Importa os pesos padrão do engine
try:
    from app.engine.scoring import DEFAULT_WEIGHTS  # type: ignore
except Exception:
    # fallback seguro
    DEFAULT_WEIGHTS = {
        "blacklist": 60,
        "watchlist": 30,
        "high_amount": 25,
        "unusual_hour": 15,
        "new_address": 40,
        "velocity": 20,
        "sensitive_token": 15,
        "sensitive_method": 20,
    }

# ------------- Aparência / CSS -------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 3rem; }
        .stButton>button { height: 42px; }
        .tight-row { margin-top: .35rem; margin-bottom: .35rem; }
        .section { border-top: 1px solid rgba(255,255,255,.1); padding-top: .8rem; margin-top: 1.2rem; }
        .muted { color: rgba(255,255,255,.6); font-size: .9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# ------------- CSV helpers (garantem arquivo e cabeçalho) -------------
def ensure_csv(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)

def read_csv(path: Path, columns: list[str]) -> pd.DataFrame:
    ensure_csv(path, columns)
    try:
        df = pd.read_csv(path)
    except Exception:
        df = pd.DataFrame(columns=columns)
    # Garante as colunas corretas
    for c in columns:
        if c not in df.columns:
            df[c] = ""
    return df[columns]

def write_csv(path: Path, df: pd.DataFrame, columns: list[str]) -> None:
    out = df.copy()
    # Só mantém as colunas esperadas, na ordem esperada
    out = out[[c for c in columns if c in out.columns]]
    out.to_csv(path, index=False)

# ------------- Pesos (carregar/salvar) -------------
def load_weights() -> dict[str, int]:
    """
    Lê pesos de weights.json, senão retorna DEFAULT_WEIGHTS.
    """
    try:
        if WEIGHTS_PATH.exists():
            with WEIGHTS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
                # Sanitiza: se faltar algo, usa default
                out = dict(DEFAULT_WEIGHTS)
                out.update({k: int(v) for k, v in (data or {}).items() if k in out})
                return out
    except Exception:
        pass
    return dict(DEFAULT_WEIGHTS)

def save_weights(weights: dict[str, int]) -> None:
    WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WEIGHTS_PATH.open("w", encoding="utf-8") as f:
        json.dump({k: int(v) for k, v in weights.items()}, f, ensure_ascii=False, indent=2)

# ------------- Cabeçalho padrão da página -------------
def render_header(title: str, subtitle: str = "") -> None:
    col_logo, col_title = st.columns([1, 9])
    with col_logo:
        st.image(ROOT / "app" / "assets" / "logo.png", width=56)
    with col_title:
        st.title(title)
        if subtitle:
            st.caption(subtitle)

# ------------- Rerun seguro (sem experimental) -------------
def safe_rerun() -> None:
    """
    Reexecuta a página garantindo compatibilidade com versões do Streamlit.
    """
    try:
        # Streamlit 1.38+ possui st.rerun
        st.rerun()
    except Exception:
        pass

# ------------- Utilidades simples -------------
def df_to_editor(df: pd.DataFrame, key: str, num_rows: str = "dynamic", use_wide: bool = True) -> pd.DataFrame:
    return st.data_editor(
        df,
        key=key,
        num_rows=num_rows,            # permite adicionar/excluir inline
        use_container_width=use_wide,
        hide_index=True,
    )
