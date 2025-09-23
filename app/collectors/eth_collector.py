# app/collectors/eth_collector.py
# Coletor on-chain (Ethereum) resiliente:
# - Prioriza Etherscan se ETHERSCAN_API_KEY estiver definida
# - Fallback automático para RPC público (Cloudflare / Llama / PublicNode)
# - Retries com backoff e NUNCA levanta exceção para fora (retorna [] em falhas)
# - Mantém filtros e o formato esperado pelo main.py

from __future__ import annotations
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests

# =============================================================================
# Parâmetros via ambiente
# =============================================================================

# ----- Etherscan -----
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()
# Lista de endereços a monitorar via Etherscan (se vazio, o coletor usará RPC)
# Ex.: "0xde0B29...,0x742d...,0x0000..."
ETHERSCAN_ADDRESSES = [a.strip() for a in os.getenv("ETHERSCAN_ADDRESSES", "").split(",") if a.strip()]
# Quantos blocos voltar para gerar o "startblock" na query do Etherscan
ETH_BLOCKS_BACK = int(os.getenv("ETH_BLOCKS_BACK", "20"))
# Máximo de transações a retornar no total (limitador de saída)
ETH_MAX_TX = int(os.getenv("ETH_MAX_TX", "100"))
# Por endereço no Etherscan (página + offset)
ETHERSCAN_MAX_TX_PER_ADDR = int(os.getenv("ETHERSCAN_MAX_TX_PER_ADDR", "100"))

# ----- RPC público (fallback) -----
RPC_URLS = [
    u.strip()
    for u in os.getenv(
        "ETH_RPC_URL",
        "https://ethereum.publicnode.com,https://eth.llamarpc.com,https://cloudflare-eth.com",
    ).split(",")
    if u.strip()
]
RPC_TIMEOUT = int(os.getenv("ETH_RPC_TIMEOUT", "25"))
RPC_RETRIES = int(os.getenv("ETH_RPC_RETRIES", "2"))
RPC_BACKOFF = float(os.getenv("ETH_RPC_BACKOFF", "0.8"))

# ----- Filtros simples -----
ONLY_ERC20 = os.getenv("ETH_ONLY_ERC20", "false").lower() == "true"  # placeholder (não usado no exemplo)
MIN_ETH_VALUE = float(os.getenv("ETH_INCLUDE_ETH_VALUE_MIN", "0.0"))

FILTER_FROM = {a.strip().lower() for a in os.getenv("ETH_FILTER_FROM", "").split(",") if a.strip()}
FILTER_TO = {a.strip().lower() for a in os.getenv("ETH_FILTER_TO", "").split(",") if a.strip()}
MONITOR_ADDR = {a.strip().lower() for a in os.getenv("ETH_MONITOR_ADDRESSES", "").split(",") if a.strip()}

# Se true, só inclui transações que casem com os filtros/monitores (reduz custo)
REQUIRE_MATCH = os.getenv("REQUIRE_MATCH", "false").lower() == "true"


# =============================================================================
# Utilidades
# =============================================================================

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
    # Heurística simples: se não tem input => TRANSFER (ETH puro), senão CALL
    if not input_data or input_data == "0x":
        return "TRANSFER"
    return "CALL"


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


# =============================================================================
# RPC público (fallback)
# =============================================================================

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

            out.append(
                {
                    "tx_id": t.get("hash", ""),
                    "timestamp": ts_iso,
                    "from_address": frm,
                    "to_address": to,
                    "amount": round(amount_eth, 6),
                    "token": "ETH",
                    "method": _tx_method(t.get("input", "")),
                    "chain": "ETH",
                }
            )
    return out


# =============================================================================
# Etherscan (preferencial se API key estiver presente)
# =============================================================================

def _etherscan_get_block_number() -> Optional[int]:
    """Usa o endpoint 'proxy' da Etherscan para pegar o blockNumber atual."""
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
    """
    Busca lista de transações para um endereço, a partir de um startblock recente.
    Limita paginação ao necessário para não passar de max_rows.
    """
    out: List[Dict[str, Any]] = []
    page = 1
    per_page = min(max_rows, 10000)  # Etherscan aceita offset até 10k
    while len(out) < max_rows:
        try:
            url = "https://api.etherscan.io/api"
            params = {
                "module": "account",
                "action": "txlist",
                "address": addr,
                "startblock": start_block,
                "endblock": 99999999,
                "page": page,
                "offset": per_page,
                "sort": "desc",
                "apikey": ETHERSCAN_API_KEY,
            }
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            j = r.json()
            if j.get("status") == "0" and j.get("message") != "OK":
                # Pode ser "No transactions found" ou rate limit. Saímos com oq temos.
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
    """
    Converte uma transação do Etherscan para o formato esperado.
    'value' no Etherscan vem como string (wei). 'timeStamp' é epoch (segundos).
    """
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
    """
    Coleta via Etherscan para os endereços de ETHERSCAN_ADDRESSES.
    Se não houver endereços configurados, devolve [] (main poderá cair no RPC).
    """
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
        # Respeito simples ao rate limit (5/s no free). Dorme uma fração.
        time.sleep(0.25)

    # Normaliza e aplica filtros
    out: List[Dict[str, Any]] = []
    for r in all_rows:
        tx = _normalize_etherscan_row(r)
        if _passes_filters(tx["from_address"], tx["to_address"], tx["amount"]):
            out.append(tx)
        if len(out) >= max_tx:
            break

    return out


# =============================================================================
# Entrada principal (chamada pelo main.py)
# =============================================================================

def load_from_eth(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Fluxo:
    1) Se ETHERSCAN_API_KEY estiver setada e ETHERSCAN_ADDRESSES tiver conteúdo,
       tenta Etherscan primeiro.
    2) Se Etherscan falhar ou vier vazio, cai para RPC público.
    Retorna sempre uma lista de dicts conforme esperado pelo motor de score.
    """
    try:
        total_limit = ETH_MAX_TX

        if ETHERSCAN_API_KEY:
            out_es = _collect_via_etherscan(total_limit)
            if out_es:
                print(f"[INFO] Coletor Etherscan retornou {len(out_es)} transações.")
                return out_es
            else:
                print("[WARN] Etherscan não retornou dados (ou endereços não configurados). Caindo para RPC...")

        out_rpc = _collect_via_rpc(total_limit)
        if out_rpc:
            print(f"[INFO] Coletor RPC retornou {len(out_rpc)} transações.")
        else:
            print("[WARN] Coletor RPC retornou 0 transações.")
        return out_rpc

    except Exception as e:
        print(f"[WARN] Erro inesperado no coletor ETH: {e}")
        return []
