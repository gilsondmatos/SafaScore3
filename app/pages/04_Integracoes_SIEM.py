# --- bootstrap de caminho ---
from pathlib import Path
import sys
_THIS = Path(__file__).resolve()
_ROOT = None
for p in _THIS.parents:
    if (p / "app").exists():
        _ROOT = p
        break
if _ROOT and str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
# --- fim bootstrap ---

import json
from typing import Dict

import requests
import streamlit as st

from app.ui.utils import DATA_DIR, list_transaction_files, load_df, render_header

st.set_page_config(page_title="Integrações SIEM", layout="wide")
render_header(st, "Integrações SIEM", "Envie eventos por Webhook (Splunk HEC / Wazuh / ELK / Qualquer HTTP)")

st.markdown("""
Use um **Webhook HTTP** (POST) para enviar eventos.
- Para **Splunk HEC**: URL do tipo `https://<host>:8088/services/collector`, Header `Authorization: Splunk <TOKEN>`.
- Para **Wazuh/ELK/Webhook.site**: informe URL e, se necessário, headers.
""")

with st.form("siem_form"):
    url = st.text_input("URL do Webhook", placeholder="https://webhook.site/xxxx ou https://splunk:8088/services/collector")
    raw_headers = st.text_area("Headers (JSON)", value='{"Content-Type":"application/json"}', height=120)
    timeout = st.number_input("Timeout (segundos)", min_value=1, max_value=60, value=15)
    send_only_crit = st.checkbox("Enviar somente críticos do arquivo selecionado", value=True)

    files = list_transaction_files()
    selected = st.selectbox("Arquivo de origem", options=files, index=len(files)-1, format_func=lambda p: p.name) if files else None

    submitted = st.form_submit_button("Enviar evento(s)")
    if submitted:
        if not url.strip():
            st.error("Informe a URL do webhook.")
        elif selected is None:
            st.error("Selecione um arquivo.")
        else:
            try:
                headers: Dict[str, str] = json.loads(raw_headers) if raw_headers.strip() else {}
            except Exception as e:
                st.error(f"Headers inválidos (JSON): {e}")
                st.stop()

            df = load_df(selected)
            if df.empty:
                st.warning("Arquivo sem dados.")
                st.stop()

            payload_rows = df[df["score"] < 50] if send_only_crit else df
            ok = 0
            fail = 0
            for rec in payload_rows.to_dict(orient="records"):
                body = json.dumps(rec, ensure_ascii=False).encode("utf-8")
                try:
                    r = requests.post(url, data=body, headers=headers, timeout=timeout)
                    if r.status_code // 100 == 2:
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1

            st.success(f"Concluído: enviados {ok}, falhas {fail}.")
