"""
CardChecker — kart puan sorgulayıcı
"""

import re
import time
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import CardResult
from ._endpoints import get_endpoints

DEFAULT_PRICE:   float = 449.98
DEFAULT_TIMEOUT: int   = 20

_HEADERS = {
    "Accept":           "application/json, text/javascript, */*; q=0.01",
    "Accept-Language":  "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent":       (
        "Mozilla/5.0 (Linux; Android 10; K) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Mobile Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Sec-Fetch-Dest":   "empty",
    "Sec-Fetch-Mode":   "cors",
    "Sec-Fetch-Site":   "same-origin",
}

_DEAD_ERRORS = {"not found"}

SITE_PRIMARY   = "a"
SITE_SECONDARY = "b"


class CardChecker:
    """
    Kart puan sorgulayıcı.

    Kullanım::

        checker = CardChecker()
        checker.set_cookies("session_id=abc123; ...")
        result = checker.check_card("4111111111111111|01|26|123")
        print(result)

    Proxy ile::

        checker = CardChecker(proxy="http://user:pass@host:port")

    İkincil endpoint ile::

        checker = CardChecker(site="b")
    """

    def __init__(
        self,
        proxy:   Optional[str] = None,
        site:    str   = SITE_PRIMARY,
        timeout: int   = DEFAULT_TIMEOUT,
        price:   float = DEFAULT_PRICE,
    ) -> None:
        self.site    = site
        self.timeout = timeout
        self.price   = price

        self._base, self._url_points, self._referer = get_endpoints(site)
        self._session = self._build_session(proxy)

    # ── Session ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_session(proxy: Optional[str]) -> requests.Session:
        session = requests.Session()
        retry   = Retry(total=2, backoff_factor=0.5,
                        status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://",  adapter)
        if proxy:
            p = proxy.strip()
            if not p.startswith(("http://", "https://", "socks5://")):
                p = "http://" + p
            session.proxies = {"http": p, "https": p}
        return session

    # ── Cookie ───────────────────────────────────────────────────────────────

    def set_cookies(self, cookie_string: str) -> None:
        """
        Cookie string'ini session'a yükler.

        ``"Cookie: name=val; ..."`` veya ``"name=val; ..."`` formatını kabul eder.
        """
        self._session.cookies.clear()
        if not cookie_string:
            return
        if cookie_string.lower().startswith("cookie:"):
            cookie_string = cookie_string[7:].strip()
        for part in cookie_string.split(";"):
            part = part.strip()
            eq   = part.find("=")
            if eq > 0:
                self._session.cookies.set(
                    part[:eq].strip(), part[eq + 1:].strip()
                )

    def get_cookies(self) -> str:
        """Mevcut cookie'leri ``name=value; ...`` formatında döndürür."""
        return "; ".join(f"{c.name}={c.value}" for c in self._session.cookies)

    # ── Bağlantı testi ───────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Hedef sunucuya HEAD isteği atarak bağlantıyı test eder."""
        try:
            r = self._session.head(
                self._base,
                headers={"User-Agent": _HEADERS["User-Agent"]},
                timeout=self.timeout,
                allow_redirects=True,
            )
            return r.status_code < 500
        except Exception:
            return False

    # ── Kart parse ───────────────────────────────────────────────────────────

    @staticmethod
    def parse_card(card_data: str) -> Optional[dict]:
        """
        Kart string'ini parse eder.

        Desteklenen ayraçlar: ``|`` ``;`` ``,`` boşluk.

        Returns:
            ``{"number", "month", "year_short", "year_full", "cvv"}``
            veya ``None`` (format hatası).
        """
        normalized = re.sub(r"[;,\s]+", "|", card_data.strip())
        parts = [p.strip() for p in normalized.split("|") if p.strip()]

        if len(parts) < 3:
            return None

        number = re.sub(r"[^0-9]", "", parts[0])
        month  = re.sub(r"[^0-9]", "", parts[1])
        year   = re.sub(r"[^0-9]", "", parts[2])
        cvv    = parts[3] if len(parts) >= 4 else ""

        if not (13 <= len(number) <= 19):
            return None
        if len(month) == 1:
            month = "0" + month
        if len(year) == 4:
            year_short, year_full = year[2:], year
        elif len(year) == 2:
            year_short, year_full = year, "20" + year
        else:
            return None

        return {
            "number":     number,
            "month":      month,
            "year_short": year_short,
            "year_full":  year_full,
            "cvv":        cvv,
        }

    # ── Ana sorgu ────────────────────────────────────────────────────────────

    def check_card(
        self,
        card_data: str,
        price: Optional[float] = None,
    ) -> CardResult:
        """
        Kartın puan bakiyesini sorgular.

        Args:
            card_data: ``"number|month|year|cvv"`` formatında kart.
                       Ayraç olarak ``|`` ``;`` ``,`` veya boşluk kullanılabilir.
            price:     Sorgu fiyatı. Belirtilmezse nesne fiyatı kullanılır.

        Returns:
            :class:`CardResult` — exception fırlatmaz, hatalar ``.error``'a yazılır.
        """
        result = CardResult(card_data=card_data)
        parsed = self.parse_card(card_data)

        if parsed is None:
            result.error = "Format hatasi (beklenen: cc|mm|yy[|cvv])"
            result.card  = card_data[:6] + "..." if len(card_data) > 6 else card_data
            return result

        result.card = parsed["number"][:4] + "****" + parsed["number"][-4:]

        return self._do_request(
            result,
            price=price if price is not None else self.price,
            **parsed,
        )

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _do_request(
        self,
        result: CardResult,
        number: str,
        month: str,
        year_short: str,
        year_full: str,
        cvv: str,
        price: float,
    ) -> CardResult:
        try:
            params = {
                "number":      number,
                "expiryMonth": month,
                "expiryYear":  year_short,
                "cvv":         cvv,
                "price":       price,
                "_":           int(time.time() * 1000),
            }
            resp = self._session.get(
                self._url_points,
                params=params,
                headers={**_HEADERS, "Referer": self._referer},
                timeout=self.timeout,
            )

            ct = resp.headers.get("Content-Type", "")
            if "text/html" in ct or resp.text.strip().startswith("<"):
                result.error = "SESSION_EXPIRED"
                return result

            if not resp.ok:
                result.error = f"HTTP {resp.status_code}"
                return result

            if not resp.text.strip():
                result.error = "Bos yanit"
                return result

            return self._parse_response(
                result, resp.json(), month, year_short, year_full, cvv, number
            )

        except requests.exceptions.Timeout:
            result.error = "Zaman asimi"
        except requests.exceptions.ConnectionError as e:
            result.error = f"Baglanti hatasi: {e}"
        except ValueError:
            result.error = "JSON parse hatasi"
        except Exception as e:
            result.error = f"Hata: {e}"

        return result

    @staticmethod
    def _parse_response(
        result: CardResult,
        data: dict,
        month: str,
        year_short: str,
        year_full: str,
        cvv: str,
        number: str,
    ) -> CardResult:
        status = data.get("status", "")

        if status.lower() == "success":
            points = float(data.get("points", 0))
            result.success    = True
            result.points     = points
            result.formatted  = f"{points:.2f} TL"
            result.bank       = data.get("bank", "Bilinmeyen")
            result.program    = data.get("cardProgramName", "")
            result.expiry     = f"{month}/{year_short}"
            result.month      = month
            result.year       = year_full
            result.cvv        = cvv
            result.full_card  = number
            result.has_points = points > 0
        else:
            msg = (
                data.get("message")
                or data.get("errorMessage")
                or f"Status: {status}"
            )
            result.error = msg

        return result

    @staticmethod
    def is_dead_error(error: Optional[str]) -> bool:
        """Hatanın kesin dead (geçersiz kart) anlamına gelip gelmediğini döndürür."""
        return bool(error) and error.strip().lower() in _DEAD_ERRORS
