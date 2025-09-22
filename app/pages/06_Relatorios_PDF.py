import io, pandas as pd, streamlit as st
from pathlib import Path
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]   # 'app' -> sobe 1 nível = raiz do projeto
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.ui.utils import list_transaction_files, load_df, load_threshold, render_header

st.set_page_config(page_title="Relatórios (PDF)", layout="wide")
render_header("Relatórios (PDF)", "Gere PDF (ou CSV) do recorte desejado")

files = list_transaction_files()
if not files:
    st.info("Nenhum CSV encontrado.")
    st.stop()

sel = st.selectbox("Arquivo", options=files, index=len(files)-1, format_func=lambda p: p.name)
df = load_df(Path(sel))
if df.empty:
    st.warning("Arquivo vazio.")
    st.stop()

thr = load_threshold(50)
modo = st.radio("Recorte", ["Críticas (< limiar)","Suspeitas (entre limiar e 70)","Todas"], horizontal=True)

def recorte(d: pd.DataFrame) -> pd.DataFrame:
    if "score" not in d.columns:
        return d.copy()
    if modo.startswith("Críticas"):
        return d[d["score"] < thr]
    if modo.startswith("Suspeitas"):
        return d[(d["score"]>=thr) & (d["score"]<70)]
    return d.copy()

rc = recorte(df)
st.caption(f"Linhas no recorte: {len(rc)}")
st.dataframe(rc.head(100), use_container_width=True, height=360)

def to_pdf(data: pd.DataFrame) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title="SafeScore Report")
        styles = getSampleStyleSheet()
        elems = [Paragraph("SafeScore — Relatório", styles["Title"]), Spacer(1,8)]
        cols = [c for c in data.columns][:10]
        tdata = [cols] + data[cols].astype(str).values.tolist()
        tbl = Table(tdata, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#23374d")),
            ("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("GRID",(0,0),(-1,-1),0.25,colors.grey),
            ("FONTSIZE",(0,0),(-1,-1),8),
        ]))
        elems.append(tbl)
        doc.build(elems)
        return buf.getvalue()
    except Exception:
        return b""

c1,c2 = st.columns(2)
with c1:
    if st.button("Gerar PDF agora"):
        if rc.empty:
            st.warning("Nada para converter.")
        else:
            pdf = to_pdf(rc)
            if pdf:
                st.success("PDF gerado.")
                st.download_button("Baixar relatorio.pdf", data=pdf, file_name="relatorio.pdf", mime="application/pdf")
            else:
                st.warning("Sem 'reportlab'. Exportando CSV do recorte.")
                st.download_button("Baixar recorte (CSV)", rc.to_csv(index=False).encode("utf-8"),
                                   file_name="relatorio_recorte.csv", mime="text/csv")
with c2:
    st.download_button("Baixar recorte (CSV)", rc.to_csv(index=False).encode("utf-8"),
                       file_name="relatorio_recorte.csv", mime="text/csv")
