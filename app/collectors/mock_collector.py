# Mock para demos/offline — gera transações sintéticas
from __future__ import annotations
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

__all__ = ["load_input_or_mock"]  # deixa claro o que exportamos

TOKENS = ["ETH", "USDT", "USDC", "DAI"]
METHODS = ["TRANSFER", "APPROVE", "SWAP"]

def _addr() -> str:
    return "0x" + "".join(random.choices("0123456789abcdef", k=40))

def _now_iso(mins: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=mins)).isoformat()

def load_input_or_mock(data_dir: Path) -> List[Dict[str, Any]]:
    """
    Gera ~12 transações mock, com uma linha 'suspeita' (valor alto / APPROVE).
    Mantém o mesmo esquema usado no coletor ETH real.
    """
    random.seed()
    out: List[Dict[str, Any]] = []

    # 12 linhas aleatórias
    for i in range(12):
        tok = random.choice(TOKENS)
        # ETH em faixa pequena; tokens em valores mais altos para simular "montante"
        val = round(random.uniform(0.01, 2.5), 8) if tok == "ETH" else round(random.uniform(5, 25000), 2)
        out.append({
            "tx_id": f"MOCK-{int(datetime.now().timestamp())}-{i}",
            "timestamp": _now_iso(random.randint(0, 120)),
            "from_address": _addr(),
            "to_address": _addr(),
            "amount": val,
            "token": tok,
            "method": random.choice(METHODS),
            "chain": "MOCK",
        })

    # 1 linha “suspeita” para testes de regra
    out.append({
        "tx_id": f"MOCK-{int(datetime.now().timestamp())}-X",
        "timestamp": _now_iso(1),
        "from_address": "0x8856599b86858a4c61cb67c26c5b1d7d41faa49d",
        "to_address": _addr(),
        "amount": 23529.2,
        "token": "USDT",
        "method": "APPROVE",
        "chain": "MOCK",
    })
    return out
