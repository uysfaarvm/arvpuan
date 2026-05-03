"""
BatchChecker — toplu kart kontrol motoru
"""

import threading
from typing import Callable, Iterable, List, Optional

from .checker import CardChecker, DEFAULT_PRICE, SITE_PRIMARY
from .models import CardResult

DEFAULT_DELAY: float = 20.0


class BatchChecker:
    """
    Kart listesini sırayla kontrol eder.

    Callbacks::

        on_result(result: CardResult)            → her kart sonucunda
        on_log(message: str)                     → log mesajı
        on_done(live, dead, error)               → tüm kartlar bitince
        on_session_expired()                     → session süresi dolunca

    Kullanım::

        batch = BatchChecker(
            cookie="...",
            on_result=lambda r: print(r),
            on_log=print,
        )
        batch.run(["4111...|01|26|123", ...])

    Notifier ile::

        from arvpuan import TelegramNotifier
        tg = TelegramNotifier(token="...", chat_id="...")

        batch = BatchChecker(
            cookie="...",
            on_result=tg.send,
            on_done=tg.send_summary,
        )
        batch.run(cards)
    """

    def __init__(
        self,
        cookie:  str   = "",
        proxy:   Optional[str] = None,
        site:    str   = SITE_PRIMARY,
        price:   float = DEFAULT_PRICE,
        delay:   float = DEFAULT_DELAY,
        on_result:          Optional[Callable[[CardResult], None]]    = None,
        on_log:             Optional[Callable[[str], None]]           = None,
        on_done:            Optional[Callable[[int, int, int], None]] = None,
        on_session_expired: Optional[Callable[[], None]]              = None,
    ) -> None:
        self.cookie  = cookie
        self.proxy   = proxy
        self.site    = site
        self.price   = price
        self.delay   = delay

        self.on_result          = on_result          or (lambda r: None)
        self.on_log             = on_log             or (lambda m: None)
        self.on_done            = on_done            or (lambda l, d, e: None)
        self.on_session_expired = on_session_expired or (lambda: None)

        self._running = False
        self._paused  = False
        self._stop_ev   = threading.Event()
        self._resume_ev = threading.Event()
        self._resume_ev.set()

        self.live_count:  int = 0
        self.dead_count:  int = 0
        self.error_count: int = 0
        self.total_cards: int = 0

        self._results: List[CardResult] = []

    # ── Kontrol ──────────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    def pause(self) -> None:
        """Döngüyü duraklatır."""
        if self._running and not self._paused:
            self._paused = True
            self._resume_ev.clear()
            self._log("Duraklatildi")

    def resume(self) -> None:
        """Duraklatılmış döngüyü devam ettirir."""
        if self._running and self._paused:
            self._paused = False
            self._resume_ev.set()
            self._log("Devam ediyor")

    def stop(self) -> None:
        """Döngüyü durdurur."""
        self._running = False
        self._paused  = False
        self._stop_ev.set()
        self._resume_ev.set()
        self._log("Durduruldu")

    def update_cookie(self, new_cookie: str) -> None:
        """Session expire sonrası yeni cookie'yi günceller."""
        self.cookie = new_cookie

    # ── Çalıştırma ───────────────────────────────────────────────────────────

    def run(
        self,
        cards:       Iterable[str],
        start_index: int  = 0,
        threaded:    bool = False,
    ) -> Optional[threading.Thread]:
        """
        Kart listesini kontrol eder.

        Args:
            cards:       Kart string'leri.
            start_index: Başlanacak indeks (kaldığı yerden devam).
            threaded:    ``True`` → arka planda thread olarak çalışır.

        Returns:
            ``threaded=True`` ise :class:`threading.Thread`, değilse ``None``.
        """
        card_list = list(cards)
        if threaded:
            t = threading.Thread(
                target=self._loop, args=(card_list, start_index), daemon=True
            )
            t.start()
            return t
        self._loop(card_list, start_index)
        return None

    def _loop(self, cards: List[str], start_index: int) -> None:
        self._running = True
        self._paused  = False
        self._stop_ev.clear()
        self._resume_ev.set()

        self.live_count  = 0
        self.dead_count  = 0
        self.error_count = 0
        self.total_cards = len(cards)
        self._results    = []

        checker = CardChecker(proxy=self.proxy, site=self.site, price=self.price)
        checker.set_cookies(self.cookie)

        self._log(
            f"Basladi — {self.total_cards} kart"
            + (f" (devam: {start_index})" if start_index > 0 else "")
        )

        i = start_index
        while i < len(cards) and self._running:
            self._resume_ev.wait()
            if not self._running:
                break

            card_data = cards[i]
            result    = checker.check_card(card_data, price=self.price)

            if result.error == "SESSION_EXPIRED":
                self._log("Session suresi doldu!")
                self.on_session_expired()
                checker.set_cookies(self.cookie)
                continue

            self._results.append(result)

            if result.is_live:
                self.live_count += 1
                full = result.full_card if result.full_card else result.card
                card_str = full + "|" + result.month + "|" + result.year + "|" + result.cvv
                self._log(f"[LIVE] {card_str} | {result.formatted} | {result.bank}")
            elif result.is_dead:
                self.dead_count += 1
                self._log(f"[DEAD] {result.card}")
            else:
                if CardChecker.is_dead_error(result.error):
                    self.dead_count += 1
                    self._log(f"[DEAD] {result.card or card_data}")
                else:
                    self.error_count += 1
                    self._log(f"[ERR]  {result.card or card_data} | {result.error}")

            self.on_result(result)
            i += 1

            if i < len(cards) and self._running and not self._paused and self.delay > 0:
                self._stop_ev.wait(timeout=self.delay)

        self._running = False
        self._log(
            f"Tamamlandi — LIVE:{self.live_count} "
            f"DEAD:{self.dead_count} ERR:{self.error_count}"
        )
        self.on_done(self.live_count, self.dead_count, self.error_count)

    # ── Sonuçlar ─────────────────────────────────────────────────────────────

    @property
    def results(self) -> List[CardResult]:
        return list(self._results)

    @property
    def live_results(self) -> List[CardResult]:
        return [r for r in self._results if r.is_live]

    def export_lives(self, filepath: str) -> None:
        """LIVE kartları ``number|month|year|cvv`` formatında dosyaya yazar."""
        with open(filepath, "w", encoding="utf-8") as f:
            for r in self.live_results:
                f.write(f"{r.full_card}|{r.month}|{r.year}|{r.cvv}\n")

    def export_all(self, filepath: str) -> None:
        """Tüm sonuçları dosyaya yazar."""
        from datetime import datetime
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            for idx, r in enumerate(self._results, 1):
                if r.is_live:
                    f.write(f"{idx}. LIVE  | {r.card_data} | {r.formatted} | {r.bank}\n")
                elif r.is_dead:
                    f.write(f"{idx}. DEAD  | {r.card_data}\n")
                else:
                    f.write(f"{idx}. ERROR | {r.card_data} | {r.error}\n")

    def _log(self, msg: str) -> None:
        self.on_log(msg)
