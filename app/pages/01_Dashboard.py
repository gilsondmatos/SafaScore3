from __future__ import annotations
import pandas as pd
import altair as alt
import streamlit as st

from app.ui.utils import (
    DATA_DIR,
    list_transaction_files,
    load_df,
    load_threshold,
    render_header,
)

# ---------- Cabeçalho ----------
render_header(
    "Dashboard",
    f"KPIs e visualizações | Dados: {DATA_DIR}"
)

# ---------- seleção de arquivo ----------
files = list_transaction_files()
if not files:
    st.info("Nenhum CSV encontrado em app/data. Gere dados na Home/Coleta local.")
    st.stop()

sel = st.selectbox(
    "Arquivo",
    options=files,
    index=len(files) - 1,
    format_func=lambda p: p.name
)

df = load_df(sel)
if df.empty:
    st.warning("Arquivo vazio ou inválido.")
    st.stop()

thr = load_threshold()

# ---------- KPIs resumidos ----------
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Transações", f"{len(df)}")
with c2:
    st.metric("Média de score", f"{df['score'].mean():.1f}")
with c3:
    st.metric("Críticas (< limiar)", f"{(df['score'] < thr).sum()}")

st.divider()

# ---------- Gráfico 1: histograma de score ----------
st.subheader("Distribuição de score")
hist = (
    alt.Chart(df)
    .mark_bar()
    .encode(
        x=alt.X("score:Q", bin=alt.Bin(step=5), title="Score"),
        y=alt.Y("count():Q", title="Contagem"),
        tooltip=["count()"]
    )
    .properties(height=240)
)
st.altair_chart(hist, use_container_width=True)

# ---------- Gráfico 2: Críticas vs OK ----------
st.subheader("Críticas vs OK (limiar atual)")
df_status = pd.DataFrame({
    "status": ["Críticas", "OK"],
    "qtd": [(df["score"] < thr).sum(), (df["score"] >= thr).sum()]
})
pie = (
    alt.Chart(df_status)
    .mark_arc(outerRadius=110)
    .encode(
        theta="qtd:Q",
        color=alt.Color("status:N", legend=None),
        tooltip=["status:N", "qtd:Q"]
    )
    .properties(height=280)
)
st.altair_chart(pie, use_container_width=True)

# ---------- Gráfico 3: Transações por token ----------
st.subheader("Transações por token")
if "token" in df.columns:
    tok = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("token:N", sort="-y", title="Token"),
            y=alt.Y("count():Q", title="Transações"),
            tooltip=["count()"]
        )
        .properties(height=260)
    )
    st.altair_chart(tok, use_container_width=True)
else:
    st.caption("Coluna 'token' não encontrada.")

# ---------- Gráfico 4: Soma de valor por token ----------
st.subheader("Soma de amount por token")
if all(c in df.columns for c in ("token", "amount")):
    df_sum = df.groupby("token", dropna=True)["amount"].sum().reset_index()
    sumbar = (
        alt.Chart(df_sum)
        .mark_bar()
        .encode(
            x=alt.X("token:N", sort="-y", title="Token"),
            y=alt.Y("amount:Q", title="Soma de amount"),
            tooltip=["amount:Q"]
        )
        .properties(height=260)
    )
    st.altair_chart(sumbar, use_container_width=True)
else:
    st.caption("Requer colunas 'token' e 'amount'.")

# ---------- Gráfico 5: média de score por hora ----------
st.subheader("Média de score por hora")
if "timestamp" in df.columns:
    df_hour = (
        df.assign(hour=df["timestamp"].dt.floor("H"))
        .groupby("hour")["score"].mean()
        .reset_index()
    )
    line = (
        alt.Chart(df_hour)
        .mark_line(point=True)
        .encode(
            x=alt.X("hour:T", title="Hora"),
            y=alt.Y("score:Q", title="Score médio"),
            tooltip=["hour:T", alt.Tooltip("score:Q", format=".1f")]
        )
        .properties(height=260)
    )
    st.altair_chart(line, use_container_width=True)
else:
    st.caption("Coluna 'timestamp' não encontrada.")

# ---------- Gráfico 6: Top remetentes com mais críticas ----------
st.subheader("Top remetentes com críticas")
if all(c in df.columns for c in ("from_address", "score")):
    bad = df[df["score"] < thr]
    if not bad.empty:
        top_from = (
            bad.groupby("from_address").size().reset_index(name="qtd").sort_values("qtd", ascending=False).head(15)
        )
        topbar = (
            alt.Chart(top_from)
            .mark_bar()
            .encode(
                x=alt.X("qtd:Q", title="Críticas"),
                y=alt.Y("from_address:N", sort="-x", title="From address"),
                tooltip=["from_address:N", "qtd:Q"]
            )
            .properties(height=360)
        )
        st.altair_chart(topbar, use_container_width=True)
    else:
        st.caption("Não há críticas com o limiar atual.")
else:
    st.caption("Requer colunas 'from_address' e 'score'.")

# ---------- Gráfico 7: Heatmap (hora x contagem) ----------
st.subheader("Heatmap: hora do dia x contagem")
if "timestamp" in df.columns:
    df_h = df.assign(h=df["timestamp"].dt.hour)
    heat = (
        alt.Chart(df_h)
        .mark_rect()
        .encode(
            x=alt.X("h:O", title="Hora (0-23)"),
            y=alt.Y("count():Q", bin=alt.Bin(maxbins=10), title="Buckets de contagem"),
            color=alt.Color("count():Q", title="Contagem"),
            tooltip=["h:O", "count()"]
        )
        .properties(height=260)
    )
    st.altair_chart(heat, use_container_width=True)
else:
    st.caption("Coluna 'timestamp' não encontrada.")
