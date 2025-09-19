from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
import os
import json
import pandas as pd
import streamlit as st

# Raiz do projeto e pasta de dados
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "app" / "data"
ASSETS_DIR = ROOT / "app" / "assets"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# --------- utilidades de leitura ---------
def load_threshold(default: int = 50) -> int:
    """Lê limiar de alerta do ambiente (fallback: default=50)."""
    try:
        return int(os.getenv("SCORE_ALERT_THRESHOLD", str(default)))
    except Exception:
        return default

def list_transaction_files() -> List[Path]:
    """Lista CSVs de transações (ex.: transactions_YYYYMMDD.csv e transactions.csv)."""
    files = sorted(DATA_DIR.glob("transactions*.csv"))
    return files

def load_df(path_or_df) -> pd.DataFrame:
    """Aceita Path ou DataFrame (para encadear chamadas)."""
    if isinstance(path_or_df, pd.DataFrame):
        return path_or_df
    p: Path = path_or_df
    if not p or not p.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(p)
        # normalizações mais comuns
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True).dt.tz_convert(None)
        for c in ("score", "amount", "penalty_total"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

# --------- UI header padrão ---------
def render_header(title: str, subtitle: str = ""):
    col1, col2 = st.columns([1, 8])
    with col1:
        logo = (ASSETS_DIR / "logo.png")
        if logo.exists():
            # Streamlit moderno usa use_column_width (não use_container_width)
            st.image(str(logo), use_column_width=True)
        else:
            st.markdown("**SafeScore**")
    with col2:
        st.title(title)
        if subtitle:
            st.caption(subtitle)

# --------- edição de listas ---------
# mapeamento: nome lógico -> (arquivo, colunas obrigatórias)
LIST_FILES: Dict[str, Tuple[Path, List[str]]] = {
    "blacklist":         (DATA_DIR / "blacklist.csv",         ["address", "reason"]),
    "watchlist":         (DATA_DIR / "watchlist.csv",         ["address", "note"]),
    "sensitive_tokens":  (DATA_DIR / "sensitive_tokens.csv",  ["token"]),
    "sensitive_methods": (DATA_DIR / "sensitive_methods.csv", ["method"]),
    "known_addresses":   (DATA_DIR / "known_addresses.csv",   ["address", "first_seen"]),
}

def _ensure_file(path: Path, columns: List[str]) -> None:
    if not path.exists():
        pd.DataFrame(columns=columns).to_csv(path, index=False)

def load_list_df(kind: str) -> Tuple[pd.DataFrame, Path, List[str]]:
    """Lê dataframe da lista (cria vazio com colunas corretas se não existir)."""
    assert kind in LIST_FILES, f"lista desconhecida: {kind}"
    path, cols = LIST_FILES[kind]
    _ensure_file(path, cols)
    try:
        df = pd.read_csv(path, dtype=str)
        # garante todas as colunas
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[cols]
    except Exception:
        df = pd.DataFrame(columns=cols)
    return df, path, cols

def save_list_df(kind: str, df: pd.DataFrame) -> None:
    path, cols = LIST_FILES[kind]
    # mantém apenas colunas conhecidas
    out = pd.DataFrame(df, columns=cols).fillna("")
    out.to_csv(path, index=False)

def download_button_for_list(kind: str, label_prefix: str = "Baixar") -> None:
    """Renderiza botão de download (fora de forms)."""
    df, path, _ = load_list_df(kind)
    st.download_button(
        label=f"{label_prefix} {path.name}",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=path.name,
        mime="text/csv",
        use_container_width=True,
    )
