from __future__ import annotations

import os
import io
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional

import pandas as pd
import streamlit as st


# --------------------------------------------------------------------
# Caminhos base
# --------------------------------------------------------------------
ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = ROOT / "app" / "data"


# --------------------------------------------------------------------
# Funções utilitárias de leitura/escrita
# --------------------------------------------------------------------
def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def list_transaction_files() -> List[Path]:
    """
    Retorna todos os CSVs de transações, ordenados por mtime (mais novo por último).
    Compatível com nomes: transactions.csv e transactions_YYYYMMDD.csv.
    """
    ensure_data_dir()
    files = list(DATA_DIR.glob("transactions*.csv"))
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def load_df(path: Path) -> pd.DataFrame:
    if not path or not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()

    # Normaliza colunas esperadas (não obriga existir)
    for col in [
        "tx_id", "timestamp", "from_address", "to_address",
        "amount", "token", "method", "chain", "score",
        "reasons", "penalty_total", "is_new_address", "velocity_last_window",
    ]:
        if col not in df.columns:
            df[col] = None

    # Parsing de tempo, se existir
    if "timestamp" in df.columns:
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        except Exception:
            pass

    return df


def write_df_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def load_threshold(default: int = 50) -> int:
    try:
        return int(os.getenv("SCORE_ALERT_THRESHOLD", str(default)))
    except Exception:
        return default


def parse_contrib_dict(text: str | Dict[str, Any] | None) -> Dict[str, float]:
    """
    Aceita:
      - string JSON contendo {"weights": {...}, "contrib_pct": {...}} ou somente um dict de pesos
      - dict já pronto
      - None
    Retorna sempre um dict simples de floats (ex.: {"blacklist": 60, ...})
    """
    if not text:
        return {}

    if isinstance(text, dict):
        d = text
    else:
        try:
            d = json.loads(text)
        except Exception:
            return {}

    # aceita payload salvo em "explain"
    if "weights" in d and isinstance(d["weights"], dict):
        return {k: float(v) for k, v in d["weights"].items() if _is_number(v)}
    # ou um dicionário direto de {regra: peso}
    return {k: float(v) for k, v in d.items() if _is_number(v)}


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------
# Cabeçalho padrão e pequenos helpers de UI
# --------------------------------------------------------------------
def render_header(st_mod, title: str, subtitle: str = "") -> Tuple[Any, Any]:
    """
    Cabeçalho consistente em todas as páginas.
    Retorna 2 colunas para uso opcional (logo + títulos).
    """
    st_mod.markdown(
        """
        <style>
        .stButton>button { border-radius: 10px; }
        .thin { font-weight: 300; color:#9aa0a6; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st_mod.columns([1, 8])
    with c1:
        st_mod.image(str(ROOT / "app" / "assets" / "logo.png"), width=64)
    with c2:
        st_mod.title(title)
        if subtitle:
            st_mod.caption(subtitle)
    st_mod.divider()
    return c1, c2


def safe_rerun():
    """
    Compatível com versões novas e antigas do Streamlit.
    """
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


def download_bytes_button(label: str, fname: str, content: bytes) -> None:
    st.download_button(
        label=label,
        file_name=fname,
        mime="text/csv",
        data=content,
        key=f"dl_{fname}",
        use_container_width=True,
    )


def info_alert(msg: str) -> None:
    st.info(msg, icon="ℹ️")


def success_alert(msg: str) -> None:
    st.success(msg, icon="✅")


def error_alert(msg: str) -> None:
    st.error(msg, icon="🚫")


# --------------------------------------------------------------------
# Carregamento/salvamento de listas (CSV)
# --------------------------------------------------------------------
def _load_simple_csv(path: Path, cols: List[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=cols)
    try:
        df = pd.read_csv(path)
        # garante colunas
        for c in cols:
            if c not in df.columns:
                df[c] = None
        return df[cols]
    except Exception:
        return pd.DataFrame(columns=cols)


def load_blacklist() -> pd.DataFrame:
    return _load_simple_csv(DATA_DIR / "blacklist.csv", ["address", "reason"])


def load_watchlist() -> pd.DataFrame:
    return _load_simple_csv(DATA_DIR / "watchlist.csv", ["address", "note"])


def load_sensitive_tokens() -> pd.DataFrame:
    return _load_simple_csv(DATA_DIR / "sensitive_tokens.csv", ["token"])


def load_sensitive_methods() -> pd.DataFrame:
    return _load_simple_csv(DATA_DIR / "sensitive_methods.csv", ["method"])


def save_csv_table(path: Path, df: pd.DataFrame, expected_cols: List[str]) -> Tuple[bool, str]:
    """
    Limpa linhas vazias, garante colunas esperadas e salva.
    """
    try:
        if df is None or df.empty:
            # cria arquivo apenas com header
            write_df_csv(path, pd.DataFrame(columns=expected_cols))
            return True, "Arquivo salvo (vazio)."
        df2 = df.copy()
        # mantém somente colunas esperadas
        for col in expected_cols:
            if col not in df2.columns:
                df2[col] = None
        df2 = df2[expected_cols]
        # limpa linhas totalmente vazias
        df2 = df2.dropna(how="all")
        # strip em textos
        for col in expected_cols:
            if df2[col].dtype == object:
                df2[col] = df2[col].astype(str).str.strip()
        write_df_csv(path, df2)
        return True, "Alterações salvas com sucesso."
    except Exception as e:
        return False, f"Falha ao salvar: {e}"
