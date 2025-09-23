# app/alerts/telegram.py
from __future__ import annotations
import os
from typing import Optional

class _NoopAlerter:
    """Alerter que não faz nada (quando não há token/chat ou não há requests)."""
    def send(self, *_args, **_kwargs) -> None:
        return

class TelegramAlerter:
    """
    Envia alertas para Telegram (opcional).
    - Só envia se TELEGRAM_TOKEN e TELEGRAM_CHAT_ID estiverem definidos.
    - 'requests' é importado tardiamente para não quebrar ambientes sem a lib.
    - Se algo der errado, falha em silêncio (pipeline não cai).
    """
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = (token or "").strip()
        self.chat_id = (chat_id or "").strip()
        self._requests = None  # lazy import

    @classmethod
    def from_env(cls) -> "TelegramAlerter | _NoopAlerter":
        token = os.getenv("TELEGRAM_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            # Sem credenciais -> no-op (não falha o app)
            return _NoopAlerter()
        return cls(token, chat_id)

    def _ensure_requests(self) -> bool:
        if self._requests is not None:
            return True
        try:
            import requests  # type: ignore
            self._requests = requests
            return True
        except Exception:
            return False

    def send(self, text: str) -> None:
        # Se faltar requests ou credencial, não faz nada
        if not self.token or not self.chat_id:
            return
        if not self._ensure_requests():
            return

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": text}
            # timeout pequeno para não travar o pipeline
            self._requests.post(url, json=payload, timeout=6)
        except Exception:
            # Nunca explode o fluxo em produção
            return
