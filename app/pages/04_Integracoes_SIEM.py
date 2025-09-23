# app/pages/04_Integracoes_SIEM.py
import sys, json, streamlit as st
from pathlib import Path

# --- bootstrap para resolver "No module named 'app'"
ROOT = Path(__file__).resolve().parents[1]  # 'app' -> sobe 1 nível (raiz do projeto)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui.utils import render_header  # render_header(st_mod, title, subtitle)

# requests é opcional
try:
    import requests
except Exception:
    requests = None

st.set_page_config(page_title="Integrações SIEM", layout="wide")

# ⚠️ AQUI estava o problema: passe o `st` como primeiro parâmetro
render_header(
    st,
    "Integrações SIEM",
    "Envie eventos por Webhook (Splunk / Wazuh / ELK / genérico)"
)

# --- formulário ---
with st.form("siem", clear_on_submit=False):
    url = st.text_input(
        "🌐 URL do Webhook",
        placeholder="https://splunk.company.com:8088/services/collector"
    )
    h_key = st.text_input("🔑 Header (chave) opcional", placeholder="Authorization")
    h_val = st.text_input("🔒 Header (valor) opcional", placeholder="Splunk <HEC_TOKEN>", type="password")
    raw = st.text_area(
        "📦 JSON do evento",
        value=json.dumps({"source": "safescore", "message": "teste"}, ensure_ascii=False, indent=2),
        height=150,
    )
    ok = st.form_submit_button("🚀 Enviar evento", use_container_width=True)

# --- envio ---
if ok:
    if not requests:
        st.error("❌ Biblioteca `requests` não instalada. Use: `pip install requests`")
    elif not url.strip():
        st.warning("⚠️ Informe a URL do webhook.")
    else:
        try:
            headers = {h_key.strip(): h_val.strip()} if h_key.strip() and h_val.strip() else {}
            payload = json.loads(raw) if raw.strip() else {}
            resp = requests.post(url.strip(), json=payload, headers=headers, timeout=10)

            if 200 <= resp.status_code < 300:
                st.success(f"✅ Evento enviado com sucesso (status {resp.status_code}).")
            else:
                st.error(f"⚠️ Erro no envio: status {resp.status_code}")

            with st.expander("📥 Resposta do servidor"):
                st.code(resp.text or "(vazio)", language="json")
        except Exception as e:
            st.error(f"❌ Falha no envio: {e}")
