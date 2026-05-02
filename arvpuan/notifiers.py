"""
Notifiers — Telegram ve Netlify bildirim entegrasyonları.

Her kart sonucu (özellikle LIVE) bu kanallardan birine veya ikisine gönderilebilir.
"""

import json
import logging
from typing import Optional

import requests

from .models import CardResult

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Telegram Bot API üzerinden kart sonuçlarını gönderir.

    Kullanım::

        tg = TelegramNotifier(token="BOT_TOKEN", chat_id="CHAT_ID")
        tg.send(result)                    # sadece LIVE gönderir (varsayılan)
        tg.send(result, only_live=False)   # hepsini gönderir

    Toplu kullanım (BatchChecker ile)::

        batch = BatchChecker(
            ...
            on_result=tg.send,
        )
    """

    _API = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        token: str,
        chat_id: str,
        only_live: bool = True,
        timeout: int = 10,
        parse_mode: str = "HTML",
    ) -> None:
        """
        Args:
            token:      Telegram bot token'ı (@BotFather'dan alınır).
            chat_id:    Mesajın gönderileceği chat/kanal ID'si.
            only_live:  ``True`` → sadece LIVE kartları gönder (varsayılan).
            timeout:    İstek zaman aşımı (saniye).
            parse_mode: ``"HTML"`` veya ``"Markdown"``.
        """
        self.token      = token
        self.chat_id    = chat_id
        self.only_live  = only_live
        self.timeout    = timeout
        self.parse_mode = parse_mode
        self._url       = self._API.format(token=token)

    def send(self, result: CardResult) -> bool:
        """
        Kart sonucunu Telegram'a gönderir.

        Args:
            result: Gönderilecek :class:`CardResult`.

        Returns:
            ``True`` → başarılı, ``False`` → başarısız.
        """
        if self.only_live and not result.is_live:
            return False

        text = self._format(result)
        try:
            resp = requests.post(
                self._url,
                json={
                    "chat_id":    self.chat_id,
                    "text":       text,
                    "parse_mode": self.parse_mode,
                },
                timeout=self.timeout,
            )
            if not resp.ok:
                logger.warning("Telegram gönderim hatası: %s", resp.text)
            return resp.ok
        except Exception as e:
            logger.error("Telegram hatası: %s", e)
            return False

    def send_summary(self, live: int, dead: int, error: int, total: int) -> bool:
        """
        Tarama özeti mesajı gönderir. BatchChecker.on_done callback'i olarak kullanılabilir.

        Örnek::

            batch = BatchChecker(
                ...
                on_done=tg.send_summary,
            )
        """
        text = (
            "<b>Tarama Tamamlandi</b>\n\n"
            f"Toplam : <code>{total}</code>\n"
            f"Live   : <code>{live}</code>\n"
            f"Dead   : <code>{dead}</code>\n"
            f"Hata   : <code>{error}</code>"
        )
        try:
            resp = requests.post(
                self._url,
                json={
                    "chat_id":    self.chat_id,
                    "text":       text,
                    "parse_mode": self.parse_mode,
                },
                timeout=self.timeout,
            )
            return resp.ok
        except Exception as e:
            logger.error("Telegram ozet hatasi: %s", e)
            return False

    @staticmethod
    def _format(result: CardResult) -> str:
        if result.is_live:
            return (
                "<b>LIVE KART</b>\n\n"
                f"Kart    : <code>{result.card}</code>\n"
                f"Puan    : <code>{result.formatted}</code>\n"
                f"Banka   : <code>{result.bank}</code>\n"
                f"Program : <code>{result.program}</code>\n"
                f"Son Kul : <code>{result.expiry}</code>"
            )
        if result.is_dead:
            return f"<b>DEAD</b>  <code>{result.card}</code>"
        return f"<b>HATA</b>  <code>{result.card or result.card_data[:20]}</code>  {result.error}"


class NetlifyNotifier:
    """
    Netlify Function (webhook) üzerinden kart sonuçlarını gönderir.

    Netlify tarafında bir serverless function kurulur; bu sınıf oraya
    JSON POST atar.

    Kullanım::

        nl = NetlifyNotifier(webhook_url="https://YOUR_SITE.netlify.app/.netlify/functions/cards")
        nl.send(result)

    Toplu kullanım::

        batch = BatchChecker(
            ...
            on_result=nl.send,
        )
    """

    def __init__(
        self,
        webhook_url: str,
        secret: Optional[str] = None,
        only_live: bool = True,
        timeout: int = 10,
    ) -> None:
        """
        Args:
            webhook_url: Netlify function URL'i.
            secret:      İsteğe bağlı paylaşılan gizli anahtar.
                         Netlify function tarafında ``X-Secret`` header'ı ile doğrulanır.
            only_live:   ``True`` → sadece LIVE kartları gönder (varsayılan).
            timeout:     İstek zaman aşımı (saniye).
        """
        self.webhook_url = webhook_url
        self.secret      = secret
        self.only_live   = only_live
        self.timeout     = timeout

    def send(self, result: CardResult) -> bool:
        """
        Kart sonucunu Netlify webhook'una gönderir.

        Returns:
            ``True`` → başarılı, ``False`` → başarısız.
        """
        if self.only_live and not result.is_live:
            return False

        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Secret"] = self.secret

        payload = result.to_dict()
        # full_card hassas veri — webhook'a gönderme
        payload.pop("full_card", None)

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if not resp.ok:
                logger.warning("Netlify gönderim hatası: %s", resp.text)
            return resp.ok
        except Exception as e:
            logger.error("Netlify hatası: %s", e)
            return False

    def send_summary(self, live: int, dead: int, error: int) -> bool:
        """
        Tarama özeti gönderir. BatchChecker.on_done callback'i olarak kullanılabilir.
        """
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Secret"] = self.secret

        try:
            resp = requests.post(
                self.webhook_url,
                json={"type": "summary", "live": live, "dead": dead, "error": error},
                headers=headers,
                timeout=self.timeout,
            )
            return resp.ok
        except Exception as e:
            logger.error("Netlify ozet hatasi: %s", e)
            return False
