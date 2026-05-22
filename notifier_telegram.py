"""
notifier_telegram.py
Kirim notifikasi hasil Market Scan ke Telegram Channel.
Dipanggil dari main.py setelah HTML di-upload ke GitHub Pages.
"""

import logging
import requests

log = logging.getLogger(__name__)


def send_telegram(config: dict, message: str) -> bool:
    """
    Kirim pesan teks ke Telegram Channel via Bot API.
    Gunakan parse_mode HTML untuk formatting.
    """
    tg_cfg = config.get("telegram", {})
    bot_token  = tg_cfg.get("bot_token", "")
    channel_id = tg_cfg.get("channel_id", "")

    if not bot_token or not channel_id:
        log.warning("[Telegram] bot_token atau channel_id belum diisi di config.json — skip notifikasi.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id":    channel_id,
        "text":       message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,  # biarkan preview muncul untuk URL
    }

    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        log.info("[Telegram] Pesan berhasil dikirim ke channel %s", channel_id)
        return True
    except requests.HTTPError as e:
        log.error("[Telegram] HTTP error: %s — %s", e, resp.text)
        return False
    except Exception as e:
        log.error("[Telegram] Gagal kirim: %s", e)
        return False


def build_message(results: list, config: dict, pages_url: str, run_time: str) -> str:
    """
    Bangun pesan Telegram dari hasil scan.
    Format: ringkasan + link ke GitHub Pages.
    """
    from datetime import datetime

    threshold   = config["score_threshold"]
    signal_kuat = [r for r in results if r.get("skor", 0) >= threshold["signal_kuat"]]
    radar       = [r for r in results if threshold["radar"] <= r.get("skor", 0) < threshold["signal_kuat"]]
    pantau      = [r for r in results if threshold["pantau"] <= r.get("skor", 0) < threshold["radar"]]

    # Format tanggal
    try:
        dt = datetime.fromisoformat(run_time)
        tgl_str = dt.strftime("%A, %d %B %Y")
        jam_str = dt.strftime("%H:%M WIB")
    except Exception:
        tgl_str = run_time
        jam_str = ""

    # Header
    lines = [
        f"📊 <b>Market Scan IDX</b>",
        f"🗓 {tgl_str}",
        "",
    ]

    # Signal summary
    if signal_kuat:
        lines.append(f"🔴 <b>Signal Kuat</b>: {len(signal_kuat)} saham")
        for r in signal_kuat[:5]:  # max 5 di pesan
            ticker = r.get("ticker", "")
            judul  = r.get("judul", "")[:60]
            skor   = r.get("skor", 0)
            ticker_str = f"<code>{ticker}</code> " if ticker else ""
            lines.append(f"   • {ticker_str}[{skor}] {judul}")
        if len(signal_kuat) > 5:
            lines.append(f"   <i>...dan {len(signal_kuat) - 5} lainnya</i>")
        lines.append("")

    if radar:
        lines.append(f"🟡 <b>Radar</b>: {len(radar)} saham")
        for r in radar[:3]:
            ticker = r.get("ticker", "")
            skor   = r.get("skor", 0)
            ticker_str = f"<code>{ticker}</code> " if ticker else ""
            lines.append(f"   • {ticker_str}[{skor}]")
        if len(radar) > 3:
            lines.append(f"   <i>...dan {len(radar) - 3} lainnya</i>")
        lines.append("")

    if pantau:
        lines.append(f"🟢 <b>Pantau</b>: {len(pantau)} saham")
        lines.append("")

    if not signal_kuat and not radar and not pantau:
        lines.append("ℹ️ Tidak ada sinyal hari ini.")
        lines.append("")

    # Link utama
    lines.append(f"🔗 <b>Laporan lengkap:</b>")
    lines.append(f"{pages_url}")
    lines.append("")
    lines.append(f"⏰ Scan selesai {jam_str}")
    lines.append("#MarketScan #IDX #Saham")

    return "\n".join(lines)
