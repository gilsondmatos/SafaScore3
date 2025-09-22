import json, streamlit as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]   # 'app' -> sobe 1 nível = raiz do projeto
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.ui.utils import render_header
try:
    import requests
except Exception:
    requests = None

st.set_page_config(page_title="Integrações SIEM", layout="wide")
render_header("Integrações SIEM", "Envie eventos por Webhook (Splunk / Wazuh / ELK / genérico)")

with st.form("siem"):
    url = st.text_input("URL do Webhook")
    h_key = st.text_input("Header (chave) opcional", placeholder="Authorization")
    h_val = st.text_input("Header (valor) opcional", placeholder="Splunk <HEC_TOKEN>")
    raw = st.text_area("JSON do evento", value=json.dumps({"source":"safescore","message":"teste"}, ensure_ascii=False, indent=2))
    ok = st.form_submit_button("Enviar")

if ok:
    if not requests:
        st.error("Instale 'requests' (pip install requests).")
    elif not url.strip():
        st.error("Informe a URL.")
    else:
        try:
            headers = {h_key.strip(): h_val.strip()} if h_key.strip() and h_val.strip() else {}
            payload = json.loads(raw) if raw.strip() else {}
            resp = requests.post(url.strip(), json=payload, headers=headers, timeout=10)
            st.success(f"Status {resp.status_code}")
            with st.expander("Resposta"):
                st.code(resp.text)
        except Exception as e:
            st.error(f"Falha: {e}")
