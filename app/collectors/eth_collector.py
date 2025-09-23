# app/collectors/eth_collector.py
from __future__ import annotations
import os, time, requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

def _get_secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st
        if name in st.secrets:
            v = st.secrets[name]
            if isinstance(v, (int, float)):
                return str(v)
            return v or default
    except Exception:
        pass
    return os.getenv(name, default)

def _get_secret_list(name: str) -> List[str]:
    import json
    raw = _get_secret(name, "")
    if not raw:
        return []
    if raw.strip().startswith("["):
        try:
            arr = json.loads(raw)
            return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    return [a.strip() for a in raw.split(",") if a.strip()]

ETHERSCAN_API_KEY = _get_secret("ETHERSCAN_API_KEY").strip()
ETHERSCAN_ADDRESSES = _get_secret_list("ETHERSCAN_ADDRESSES")
ETH_BLOCKS_BACK = int(_get_secret("ETH_BLOCKS_BACK", "20"))
ETH_MAX_TX = int(_get_secret("ETH_MAX_TX", "100"))
ETHERSCAN_MAX_TX_PER_ADDR = int(_get_secret("ETHERSCAN_MAX_TX_PER_ADDR", "100"))

RPC_URLS = [u.strip() for u in _get_secret(
    "ETH_RPC_URL",
    "https://ethereum.publicnode.com,https://eth.llamarpc.com,https://cloudflare-eth.com"
).split(",") if u.strip()]
RPC_TIMEOUT = int(_get_secret("ETH_RPC_TIMEOUT", "25"))
RPC_RETRIES = int(_get_secret("ETH_RPC_RETRIES", "2"))
RPC_BACKOFF = float(_get_secret("ETH_RPC_BACKOFF", "0.8"))

ONLY_ERC20 = _get_secret("ETH_ONLY_ERC20", "false").lower() == "true"
MIN_ETH_VALUE = float(_get_secret("ETH_INCLUDE_ETH_VALUE_MIN", "0.0"))
FILTER_FROM = {a.strip().lower() for a in _get_secret("ETH_FILTER_FROM", "").split(",") if a.strip()}
FILTER_TO = {a.strip().lower() for a in _get_secret("ETH_FILTER_TO", "").split(",") if a.strip()}
MONITOR_ADDR = {a.strip().lower() for a in _get_secret("ETH_MONITOR_ADDRESSES", "").split(",") if a.strip()}
REQUIRE_MATCH = _get_secret("REQUIRE_MATCH", "false").lower() == "true"

def _hex_to_int(x: Optional[str]) -> int:
    try:
        return int(x or "0x0", 16)
    except Exception:
        return 0

def _wei_to_eth_from_hex(wei_hex: Optional[str]) -> float:
    return _hex_to_int(wei_hex) / 1e18

def _wei_to_eth_from_str(wei_str: Optional[str]) -> float:
    try:
        return float(wei_str) / 1e18
    except Exception:
        try:
            return float(wei_str or 0.0)
        except Exception:
            return 0.0

def _block_ts_to_iso(ts_hex: Optional[str]) -> str:
    ts = _hex_to_int(ts_hex)
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

def _to_iso_from_int(ts_int: int) -> str:
    try:
        return datetime.fromtimestamp(int(ts_int), tz=timezone.utc).isoformat()
    except Exception:
        return ""

def _tx_method(input_data: str) -> str:
    return "TRANSFER" if (not input_data or input_data == "0x") else "CALL"

def _passes_filters(tx_from: str, tx_to: str, amount_eth: float) -> bool:
    fa = (tx_from or "").lower()
    ta = (tx_to or "").lower()
    if MIN_ETH_VALUE and amount_eth < MIN_ETH_VALUE:
        return False
    has_monitor = (MONITOR_ADDR and (fa in MONITOR_ADDR or ta in MONITOR_ADDR))
    has_from = (FILTER_FROM and fa in FILTER_FROM)
    has_to = (FILTER_TO and ta in FILTER_TO)
    if REQUIRE_MATCH:
        return has_monitor or has_from or has_to
    if FILTER_FROM and fa not in FILTER_FROM:
        return False
    if FILTER_TO and ta not in FILTER_TO:
        return False
    return True

def _rpc_any(method: str, params: list) -> Optional[Dict[str, Any] | Any]:
    last_err: Optional[Exception] = None
    for url in RPC_URLS:
        for attempt in range(RPC_RETRIES):
            try:
                r = requests.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                    timeout=RPC_TIMEOUT,
                )
                r.raise_for_status()
                j = r.json()
                if j.get("error"):
                    last_err = RuntimeError(str(j["error"]))
                else:
                    return j.get("result")
            except Exception as e:
                last_err = e
                time.sleep(RPC_BACKOFF * (attempt + 1))
    if last_err:
        print(f"[WARN] RPC falhou para {method} em todas URLs: {last_err}")
    return None

def _collect_via_rpc(max_tx: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    head_hex = _rpc_any("eth_blockNumber", [])
    if not head_hex:
        print("[WARN] Não foi possível obter o blockNumber via RPC.")
        return out
    head = _hex_to_int(head_hex)
    start = max(0, head - ETH_BLOCKS_BACK)
    for n in range(head, start - 1, -1):
        if len(out) >= max_tx:
            break
        blk = _rpc_any("eth_getBlockByNumber", [hex(n), True]) or {}
        if not blk:
            continue
        ts_iso = _block_ts_to_iso(blk.get("timestamp"))
        txs = blk.get("transactions") or []
        for t in txs:
            if len(out) >= max_tx:
                break
            frm = t.get("from") or ""
            to = t.get("to") or ""
            amount_eth = _wei_to_eth_from_hex(t.get("value"))
            if not _passes_filters(frm, to, amount_eth):
                continue
            out.append({
                "tx_id": t.get("hash", ""),
                "timestamp": ts_iso,
                "from_address": frm,
                "to_address": to,
                "amount": round(amount_eth, 6),
                "token": "ETH",
                "method": _tx_method(t.get("input", "")),
                "chain": "ETH",
            })
    return out

def _etherscan_get_block_number() -> Optional[int]:
    try:
        url = "https://api.etherscan.io/api"
        params = {"module": "proxy", "action": "eth_blockNumber", "apikey": ETHERSCAN_API_KEY}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        j = r.json()
        res = j.get("result")
        if res and isinstance(res, str) and res.startswith("0x"):
            return int(res, 16)
    except Exception as e:
        print(f"[WARN] Falha ao obter blockNumber via Etherscan: {e}")
    return None

def _etherscan_txlist(addr: str, start_block: int, max_rows: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page, per_page = 1, min(max_rows, 10000)
    while len(out) < max_rows:
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account", "action": "txlist", "address": addr,
                "startblock": start_block, "endblock": 99999999,
                "page": page, "offset": per_page, "sort": "desc",
                "apikey": ETHERSCAN_API_KEY,
            }
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            j = r.json()
            if j.get("status") == "0" and j.get("message") != "OK":
                break
            rows = j.get("result") or []
            if not rows:
                break
            out.extend(rows)
            if len(rows) < per_page:
                break
            page += 1
        except Exception as e:
            print(f"[WARN] Falha em txlist para {addr}: {e}")
            break
    return out[:max_rows]

def _normalize_etherscan_row(row: Dict[str, Any]) -> Dict[str, Any]:
    frm = row.get("from", "")
    to = row.get("to", "")
    amount_eth = _wei_to_eth_from_str(row.get("value"))
    return {
        "tx_id": row.get("hash", ""),
        "timestamp": _to_iso_from_int(int(row.get("timeStamp", "0"))),
        "from_address": frm,
        "to_address": to,
        "amount": round(amount_eth, 6),
        "token": "ETH",
        "method": _tx_method(row.get("input", "")),
        "chain": "ETH",
    }

def _collect_via_etherscan(max_tx: int) -> List[Dict[str, Any]]:
    if not ETHERSCAN_ADDRESSES:
        return []
    head = _etherscan_get_block_number()
    if not head:
        return []
    start_block = max(0, head - ETH_BLOCKS_BACK)
    all_rows: List[Dict[str, Any]] = []
    for addr in ETHERSCAN_ADDRESSES:
        if len(all_rows) >= max_tx:
            break
        rows = _etherscan_txlist(addr, start_block, min(ETHERSCAN_MAX_TX_PER_ADDR, max_tx - len(all_rows)))
        all_rows.extend(rows)
        time.sleep(0.25)
    out: List[Dict[str, Any]] = []
    for r in all_rows:
        tx = _normalize_etherscan_row(r)
        if _passes_filters(tx["from_address"], tx["to_address"], tx["amount"]):
            out.append(tx)
        if len(out) >= max_tx:
            break
    return out

def load_from_eth(data_dir: Path) -> List[Dict[str, Any]]:
    try:
        total_limit = ETH_MAX_TX
        if ETHERSCAN_API_KEY:
            out_es = _collect_via_etherscan(total_limit)
            if out_es:
                print(f"[INFO] Coletor Etherscan retornou {len(out_es)} transações.")
                return out_es
            else:
                print("[WARN] Etherscan não retornou dados. Caindo para RPC…")
        out_rpc = _collect_via_rpc(total_limit)
        if out_rpc:
            print(f"[INFO] Coletor RPC retornou {len(out_rpc)} transações.")
        else:
            print("[WARN] Coletor RPC retornou 0 transações.")
        return out_rpc
    except Exception as e:
        print(f"[WARN] Erro inesperado no coletor ETH: {e}")
        return []
