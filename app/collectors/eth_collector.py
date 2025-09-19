# app/collectors/eth_collector.py
# Coletor on-chain (Ethereum) resiliente: faz failover entre várias RPCs públicas,
# aplica retries com backoff e NUNCA levanta exceção para fora (retorna [] se falhar).
# Comentários em PT-BR para facilitar manutenção e defesa técnica.

from __future__ import annotations
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests

# ---------- Parâmetros por ambiente (ajustáveis sem mudar código) ----------
# Lista de RPCs (separadas por vírgula) – usaremos failover de forma automática
RPC_URLS = [
    u.strip()
    for u in os.getenv(
        "ETH_RPC_URL",
        "https://ethereum.publicnode.com,https://eth.llamarpc.com,https://cloudflare-eth.com",
    ).split(",")
    if u.strip()
]

# Timeout de cada chamada HTTP ao RPC (segundos)
RPC_TIMEOUT = int(os.getenv("ETH_RPC_TIMEOUT", "25"))
# Quantidade de retries por URL antes de tentar a próxima URL
RPC_RETRIES = int(os.getenv("ETH_RPC_RETRIES", "2"))
# Backoff (segundos) entre tentativas consecutivas
RPC_BACKOFF = float(os.getenv("ETH_RPC_BACKOFF", "0.8"))

# Janela de blocos a voltar e limite de transações
ETH_BLOCKS_BACK = int(os.getenv("ETH_BLOCKS_BACK", "20"))
ETH_MAX_TX = int(os.getenv("ETH_MAX_TX", "100"))

# Filtros simples
ONLY_ERC20 = os.getenv("ETH_ONLY_ERC20", "false").lower() == "true"  # placeholder
MIN_ETH_VALUE = float(os.getenv("ETH_INCLUDE_ETH_VALUE_MIN", "0.0"))

FILTER_FROM = {a.strip().lower() for a in os.getenv("ETH_FILTER_FROM", "").split(",") if a.strip()}
FILTER_TO = {a.strip().lower() for a in os.getenv("ETH_FILTER_TO", "").split(",") if a.strip()}
MONITOR_ADDR = {a.strip().lower() for a in os.getenv("ETH_MONITOR_ADDRESSES", "").split(",") if a.strip()}

# Se true, só inclui transações que casem com os filtros/monitores (reduz custo)
REQUIRE_MATCH = os.getenv("REQUIRE_MATCH", "false").lower() == "true"


# ---------- Utilidades ----------
def _hex_to_int(x: Optional[str]) -> int:
    try:
        return int(x or "0x0", 16)
    except Exception:
        return 0


def _wei_to_eth(wei_hex: Optional[str]) -> float:
    # Converte valor em wei (hex) para ETH (float)
    return _hex_to_int(wei_hex) / 1e18


def _rpc_any(method: str, params: list) -> Optional[Dict[str, Any] | Any]:
    """
    Faz a chamada JSON-RPC tentando cada URL com retries e backoff.
    Retorna o "result" do RPC ou None se todas as tentativas falharem.
    """
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
                    # erro lógico do nó – tenta próxima tentativa/URL
                else:
                    return j.get("result")
            except Exception as e:
                last_err = e
                time.sleep(RPC_BACKOFF * (attempt + 1))
        # esgota tentativas desta URL -> tenta a próxima
    if last_err:
        print(f"[WARN] RPC falhou para {method} em todas URLs: {last_err}")
    return None


def _block_ts_to_iso(ts_hex: Optional[str]) -> str:
    ts = _hex_to_int(ts_hex)
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _tx_method(input_data: str) -> str:
    # Heurística simples para classificar o método (CALL/TRANSFER)
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
        # Quando ativo, só passa se casar com algum filtro/monitor
        return has_monitor or has_from or has_to

    # Quando não obrigatório, passa sempre (a não ser que filtros explícitos
    # estejam definidos e não casem – regra comum em demos)
    if FILTER_FROM and fa not in FILTER_FROM:
        return False
    if FILTER_TO and ta not in FILTER_TO:
        return False

    return True


# ---------- Entrada principal do coletor ----------
def load_from_eth(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Coleta últimos blocos da rede, aplica filtros leves e retorna lista de transações
    no formato esperado pelo motor de scoring. Em caso de falha, retorna [].
    """
    out: List[Dict[str, Any]] = []

    head_hex = _rpc_any("eth_blockNumber", [])
    if not head_hex:
        print("[WARN] Não foi possível obter o blockNumber.")
        return []

    head = _hex_to_int(head_hex)
    start = max(0, head - ETH_BLOCKS_BACK)

    for n in range(head, start - 1, -1):
        if len(out) >= ETH_MAX_TX:
            break

        blk = _rpc_any("eth_getBlockByNumber", [hex(n), True]) or {}
        if not blk:
            continue

        ts_iso = _block_ts_to_iso(blk.get("timestamp"))
        txs = blk.get("transactions") or []

        for t in txs:
            if len(out) >= ETH_MAX_TX:
                break

            # Apenas ETH transfers simples (o coletor pode ser expandido para ERC-20)
            frm = t.get("from") or ""
            to = t.get("to") or ""
            amount_eth = _wei_to_eth(t.get("value"))

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

    if not out:
        print("[WARN] Coletor ETH retornou 0 transações (filtros/monitores podem estar muito restritivos).")
    else:
        print(f"[INFO] Coletor ETH retornou {len(out)} transações.")

    return out
