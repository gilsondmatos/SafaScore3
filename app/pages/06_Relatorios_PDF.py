# app/pages/06_Relatorios_PDF.py
from __future__ import annotations

# --------------------------------------------------------------------
# Bootstrap para rodar via: streamlit run app/pages/06_Relatorios_PDF.py
# --------------------------------------------------------------------
import sys, io
from pathlib import Path

_THIS = Path(__file__).resolve()
for parent in _THIS.parents:
    if (parent / "app").is_dir():
        _PROJ = parent
        break
else:
    _PROJ = _THIS.parent

if str(_PROJ) not in sys.path:
    sys.path.insert(0, str(_PROJ))

# --------------------------------------------------------------------
import pandas as pd
import streamlit as st

from app.ui.utils import (
    list_transaction_files,
    load_df,
    load_threshold,
    render_header,
)

# ==================== UI (Streamlit) ====================
st.set_page_config(page_title="Relatórios (PDF)", layout="wide")
# render_header aceita st ou não, de acordo com sua util
try:
    render_header("Relatórios (PDF)", "Gere PDF (ou CSV) do recorte desejado")
except Exception:
    render_header(st, "Relatórios (PDF)", "Gere PDF (ou CSV) do recorte desejado")

files = list_transaction_files()
if not files:
    st.info("Nenhum CSV encontrado em app/data. Vá em **Home → Coletar agora (ETH)**.")
    st.stop()

sel = st.selectbox(
    "Arquivo",
    options=files,
    index=len(files) - 1,
    format_func=lambda p: p.name,
)

df = load_df(Path(sel))
if df.empty:
    st.warning("Arquivo selecionado está vazio.")
    st.stop()

thr = load_threshold(50)

modo = st.radio(
    "Recorte",
    ["Críticas (< limiar)", "Suspeitas (entre limiar e 70)", "Todas"],
    horizontal=True,
)

# ==================== Lógica de recorte ====================
def recorte(d: pd.DataFrame) -> pd.DataFrame:
    if "score" not in d.columns:
        return d.copy()
    if modo.startswith("Críticas"):
        return d[d["score"] < thr]
    if modo.startswith("Suspeitas"):
        return d[(d["score"] >= thr) & (d["score"] < 70)]
    return d.copy()

rc = recorte(df).reset_index(drop=True)
st.caption(f"Linhas no recorte: {len(rc)}")

# Mostramos um conjunto "principal" de colunas (legível) e,
# em um expander, o DataFrame completo:
MAIN_COLS = [c for c in [
    "tx_id", "timestamp", "from_address", "to_address",
    "amount", "token", "method", "score"
] if c in rc.columns]

if MAIN_COLS:
    st.dataframe(rc[MAIN_COLS].head(100), use_container_width=True, height=360)
else:
    # fallback se não tiver as colunas principais
    st.dataframe(rc.head(100), use_container_width=True, height=360)

with st.expander("Ver todas as colunas (recorte completo)"):
    st.dataframe(rc, use_container_width=True, height=460)

# ==================== PDF Helper ====================
def _compute_column_widths(df: pd.DataFrame, cols: list[str], total_width: float) -> list[float]:
    """
    Calcula larguras proporcionais por coluna para caber no total_width.
    Aproximação por número de caracteres (título + células),
    com limites mínimo e máximo por coluna.
    """
    if not cols:
        return []

    # parâmetros de layout
    MIN_W = 60.0     # largura mínima por coluna (pt)
    MAX_W = 260.0    # largura máxima por coluna (pt)
    CHAR_PT = 4.0    # pontos por caractere (aprox.)

    # mede "peso" por coluna
    weights = []
    for c in cols:
        header_len = len(str(c))
        sample = df[c].astype(str).head(400).tolist() if c in df.columns else []
        avg_len = (sum(len(s) for s in sample) / max(1, len(sample))) if sample else 10
        # peso bruto por coluna
        w = (header_len * 0.6 + avg_len) * CHAR_PT
        weights.append(w)

    # normaliza ao intervalo [MIN_W, MAX_W] antes de escalar
    weights = [min(MAX_W, max(MIN_W, w)) for w in weights]

    # escala para caber no total_width
    s = sum(weights)
    if s == 0:
        return [total_width / len(cols)] * len(cols)
    scale = total_width / s
    widths = [w * scale for w in weights]

    # Se por arredondamento sobrar/ faltar, ajusta levemente a última coluna
    diff = total_width - sum(widths)
    if widths:
        widths[-1] += diff
    return widths

def df_to_pdf_bytes(data: pd.DataFrame, cols: list[str]) -> bytes:
    """
    Gera PDF em A4 paisagem com margens mínimas e colunas ajustadas.
    """
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle,
            Paragraph, Spacer, PageBreak
        )
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet

        buf = io.BytesIO()

        # A4 paisagem
        PAGE_W, PAGE_H = landscape(A4)
        # Margens mínimas
        MARGIN = 8  # ~3mm
        doc = SimpleDocTemplate(
            buf,
            pagesize=(PAGE_W, PAGE_H),
            leftMargin=MARGIN,
            rightMargin=MARGIN,
            topMargin=MARGIN,
            bottomMargin=MARGIN,
            title="SafeScore Report"
        )

        styles = getSampleStyleSheet()
        elems = []
        title = Paragraph("SafeScore — Relatório", styles["Title"])
        elems.append(title)
        elems.append(Spacer(1, 6))

        # dados para tabela:
        use_cols = [c for c in cols if c in data.columns]
        if not use_cols:
            use_cols = list(data.columns)

        # limita linhas por página (tabela grande costuma ficar pesada);
        # mas o reportlab quebra automaticamente se passar da página
        # por segurança, não vamos quebrar manualmente — deixamos rolar.
        table_data = [use_cols] + data[use_cols].astype(str).values.tolist()

        # calcula larguras totais que caibam na página (descontando margens)
        usable_w = PAGE_W - (MARGIN * 2)
        col_widths = _compute_column_widths(data, use_cols, usable_w)

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#23374d")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
            ("GRID",       (0, 0), (-1, -1), 0.25, colors.grey),
            ("FONTSIZE",   (0, 0), (-1, -1), 7),   # fonte compacta
            ("BOTTOMPADDING",(0,0),(-1,-1), 2),
            ("TOPPADDING", (0,0),(-1,-1), 2),
        ]))

        elems.append(tbl)
        doc.build(elems)
        return buf.getvalue()
    except Exception:
        # Se não tiver reportlab ou algo falhar, devolvemos bytes vazios
        return b""

# ==================== Ações (PDF / CSV) ====================
c1, c2 = st.columns(2)
with c1:
    if st.button("Gerar PDF agora", use_container_width=True):
        if rc.empty:
            st.warning("Nada para converter.")
        else:
            pdf = df_to_pdf_bytes(rc, MAIN_COLS if MAIN_COLS else list(rc.columns))
            if pdf:
                st.success("PDF gerado.")
                st.download_button(
                    "Baixar relatorio.pdf",
                    data=pdf,
                    file_name="relatorio.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            else:
                st.warning("Biblioteca 'reportlab' não disponível. Exporte o CSV do recorte.")
with c2:
    st.download_button(
        "Baixar recorte (CSV)",
        rc.to_csv(index=False).encode("utf-8"),
        file_name=f"relatorio_recorte_{Path(sel).stem}.csv",
        mime="text/csv",
        use_container_width=True
    )
