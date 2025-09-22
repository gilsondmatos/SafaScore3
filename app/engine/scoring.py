# app/engine/scoring.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Set
from datetime import datetime, timedelta, timezone
import csv
import json
import os

# ------------------------------------------------------------
# Pesos default (usados se não existir override em JSON)
# ------------------------------------------------------------
DEFAULT_WEIGHTS: Dict[str, int] = {
    "blacklist": 60,
    "watchlist": 30,
    "high_amount": 25,
    "unusual_hour": 15,
    "new_address": 40,
    "velocity": 20,
    "sensitive_token": 15,
    "sensitive_method": 15,
}

ENGINE_DIR = Path(__file__).resolve().parent
OVERRIDE = ENGINE_DIR / "weights_override.json"

def _load_weights() -> Dict[str, int]:
    """Carrega pesos com override se weights_override.json existir."""
    if OVERRIDE.exists():
        try:
            data = json.loads(OVERRIDE.read_text(encoding="utf-8"))
            # valida somente chaves conhecidas
            out = dict(DEFAULT_WEIGHTS)
            for k, v in data.items():
                if k in out:
                    out[k] = int(v)
            return out
        except Exception:
            # se o override estiver corrompido, ignora
            pass
    return dict(DEFAULT_WEIGHTS)


# ------------------------------------------------------------
# Utilidades de parsing
# ------------------------------------------------------------
def _to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return default

def _parse_ts(ts: str | None) -> datetime:
    """Aceita ISO 8601; fallback: agora (UTC)."""
    if not ts:
        return datetime.now(timezone.utc)
    try:
        # Tenta com timezone; se vier naive, assume UTC
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)

def _lower(x: Any) -> str:
    return str(x or "").strip().lower()


# ------------------------------------------------------------
# Classe principal usada pela sua main.py
# ------------------------------------------------------------
class ScoreEngine:
    """
    ScoreEngine(data_dir, prev_transactions, known_addresses)

    - data_dir: diretório com CSVs de listas (blacklist.csv, watchlist.csv etc.)
    - prev_transactions: lista de dicts (linhas do CSV anterior) para janela de velocidade e "novo endereço"
    - known_addresses: set de endereços já conhecidos (para regra new_address)
    """

    def __init__(
        self,
        data_dir: str,
        prev_transactions: List[Dict[str, Any]] | None = None,
        known_addresses: Set[str] | None = None,
    ):
        self.data_dir = Path(data_dir)
        self.prev = prev_transactions or []
        self.known = { _lower(a) for a in (known_addresses or set()) }
        self.weights = _load_weights()

        # parâmetros via env (com defaults sensatos)
        self.amount_threshold = _to_float(os.getenv("AMOUNT_THRESHOLD", "10000"), 10000.0)

        self.velocity_window_min = int(os.getenv("VELOCITY_WINDOW_MIN", "10"))   # janela em minutos
        self.velocity_max_tx = int(os.getenv("VELOCITY_MAX_TX", "5"))            # max txs na janela

        # Carrega listas auxiliares
        self.blacklist = self._load_single_column_csv("blacklist.csv", "address")
        self.watchlist = self._load_single_column_csv("watchlist.csv", "address")
        self.sensitive_tokens = self._load_single_column_csv("sensitive_tokens.csv", "token")
        self.sensitive_methods = self._load_single_column_csv("sensitive_methods.csv", "method")

    # ------------------ Leitura de CSVs de listas ------------------
    def _load_single_column_csv(self, file_name: str, col: str) -> Set[str]:
        p = self.data_dir / file_name
        out: Set[str] = set()
        if not p.exists():
            return out
        try:
            with p.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    v = _lower(row.get(col))
                    if v:
                        out.add(v)
        except Exception:
            pass
        return out

    # ------------------ Regras ------------------
    def _rule_blacklist(self, from_addr: str, to_addr: str, hits: Dict[str, int], reasons: List[str]):
        if from_addr in self.blacklist or to_addr in self.blacklist:
            w = self.weights["blacklist"]
            hits["blacklist"] = w
            reasons.append("Endereço em blacklist")

    def _rule_watchlist(self, from_addr: str, to_addr: str, hits: Dict[str, int], reasons: List[str]):
        if from_addr in self.watchlist or to_addr in self.watchlist:
            w = self.weights["watchlist"]
            hits["watchlist"] = w
            reasons.append("Endereço em watchlist")

    def _rule_high_amount(self, amount: float, token: str, hits: Dict[str, int], reasons: List[str]):
        # regra simples: valor numérico acima do limite (independe de token)
        if amount >= self.amount_threshold:
            w = self.weights["high_amount"]
            hits["high_amount"] = w
            reasons.append(f"Valor alto (>= {self.amount_threshold:g})")

    def _rule_unusual_hour(self, ts: datetime, hits: Dict[str, int], reasons: List[str]):
        # Considera horário incomum 00:00–05:59
        if 0 <= ts.hour <= 5:
            w = self.weights["unusual_hour"]
            hits["unusual_hour"] = w
            reasons.append("Horário incomum (madrugada)")

    def _rule_new_address(self, from_addr: str, hits: Dict[str, int], reasons: List[str]):
        if from_addr and (from_addr not in self.known):
            w = self.weights["new_address"]
            hits["new_address"] = w
            reasons.append("Endereço remetente não conhecido")

    def _rule_velocity(self, ts: datetime, from_addr: str, hits: Dict[str, int], reasons: List[str]) -> int:
        # Quantas transações esse remetente teve na janela de VELOCITY_WINDOW_MIN minutos (dados anteriores)
        if not from_addr or not self.prev:
            return 0

        window_start = ts - timedelta(minutes=self.velocity_window_min)
        cnt = 0
        for row in self.prev:
            try:
                faddr = _lower(row.get("from_address"))
                if faddr != from_addr:
                    continue
                rts = _parse_ts(row.get("timestamp"))
                if window_start <= rts <= ts:
                    cnt += 1
            except Exception:
                continue

        if cnt > self.velocity_max_tx:
            w = self.weights["velocity"]
            hits["velocity"] = w
            reasons.append(f"Velocidade alta ({cnt} txs em {self.velocity_window_min}min)")
        return cnt

    def _rule_sensitive_token(self, token: str, hits: Dict[str, int], reasons: List[str]):
        if token in self.sensitive_tokens:
            w = self.weights["sensitive_token"]
            hits["sensitive_token"] = w
            reasons.append(f"Token sensível ({token})")

    def _rule_sensitive_method(self, method: str, hits: Dict[str, int], reasons: List[str]):
        if method in self.sensitive_methods:
            w = self.weights["sensitive_method"]
            hits["sensitive_method"] = w
            reasons.append(f"Método sensível ({method})")

    # ------------------ API pública ------------------
    def score_transaction(self, tx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retorna:
        {
            "score": int (100 - soma das penalidades),
            "hits": { regra: peso, ... },
            "reasons": [str],
            "velocity_last_window": int
        }
        """
        hits: Dict[str, int] = {}
        reasons: List[str] = []

        # Normaliza campos
        from_addr = _lower(tx.get("from_address"))
        to_addr = _lower(tx.get("to_address"))
        token = _lower(tx.get("token"))
        method = _lower(tx.get("method"))
        amount = _to_float(tx.get("amount"), 0.0)
        ts = _parse_ts(tx.get("timestamp"))

        # Aplica regras
        self._rule_blacklist(from_addr, to_addr, hits, reasons)
        self._rule_watchlist(from_addr, to_addr, hits, reasons)
        self._rule_high_amount(amount, token, hits, reasons)
        self._rule_unusual_hour(ts, hits, reasons)
        self._rule_new_address(from_addr, hits, reasons)
        vel_cnt = self._rule_velocity(ts, from_addr, hits, reasons)
        self._rule_sensitive_token(token, hits, reasons)
        self._rule_sensitive_method(method, hits, reasons)

        penalty = sum(hits.values())
        score = max(0, 100 - penalty)

        return {
            "score": int(score),
            "hits": hits,
            "reasons": reasons,
            "velocity_last_window": vel_cnt,
        }
