"""
main.py
Orkestrator utama — scraping 8 sumber, analisis Claude API, render HTML,
upload ke GitHub Pages, kirim notifikasi Telegram.
"""

import json
import logging
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "scraper.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def load_config() -> dict:
    cfg_path = os.path.join(BASE_DIR, "config.json")
    if not os.path.exists(cfg_path):
        log.error("config.json tidak ditemukan di: %s", cfg_path)
        sys.exit(1)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    key = cfg.get("anthropic_api_key", "")
    if not key or "DIISI" in key:
        log.error("API key belum diisi di config.json!")
        sys.exit(1)
    return cfg


def simpan_ke_db(articles_with_scores: list):
    from scraper import simpan_artikel
    for artikel in articles_with_scores:
        simpan_artikel(artikel)
    log.info("Disimpan %d artikel ke database.", len(articles_with_scores))


def main():
    run_time = datetime.now().isoformat()
    log.info("=" * 60)
    log.info("Market Scan dimulai: %s", run_time)
    log.info("=" * 60)

    cfg = load_config()
    log.info("Config berhasil dimuat.")

    try:
        from scraper           import init_db, url_sudah_ada
        from scraper_cnbc      import run_cnbc_rss_scraper
        from scraper_bloomberg import run_bloomberg_scraper
        from scraper_idxchannel    import run_idxchannel_scraper
        from scraper_idnfinancials import run_idnfinancials_scraper
        from scraper_emitennews    import run_emitennews_scraper
        from scraper_investorid    import run_investorid_scraper
        from scraper_kontan        import run_kontan_scraper
        from scraper_liputan6      import run_liputan6_scraper
        from analyzer          import analyze_articles
        from renderer          import save_html
        from publisher_github  import publish_to_github
        from notifier_telegram import build_message, send_telegram
    except ImportError as e:
        log.error("Import error: %s", e)
        sys.exit(1)

    # ── Init DB ──────────────────────────────────────────────────
    init_db()

    # ── Step 1: Scraping ─────────────────────────────────────────
    log.info("STEP 1: Scraping 8 sumber berita...")
    articles_all = []

    log.info("  [1/8] CNBC Indonesia (RSS)...")
    r = run_cnbc_rss_scraper(cfg, url_sudah_ada)
    log.info("  CNBC: %d artikel", len(r))
    articles_all.extend(r)

    log.info("  [2/8] Bloomberg Technoz...")
    r = run_bloomberg_scraper(cfg, url_sudah_ada)
    log.info("  Bloomberg: %d artikel", len(r))
    articles_all.extend(r)

    log.info("  [3/8] IDX Channel...")
    r = run_idxchannel_scraper(cfg, url_sudah_ada)
    log.info("  IDX Channel: %d artikel", len(r))
    articles_all.extend(r)

    log.info("  [4/8] IDN Financials...")
    r = run_idnfinancials_scraper(cfg, url_sudah_ada)
    log.info("  IDN Financials: %d artikel", len(r))
    articles_all.extend(r)

    log.info("  [5/8] Emiten News...")
    r = run_emitennews_scraper(cfg, url_sudah_ada)
    log.info("  Emiten News: %d artikel", len(r))
    articles_all.extend(r)

    log.info("  [6/8] Investor.ID...")
    r = run_investorid_scraper(cfg, url_sudah_ada)
    log.info("  Investor.ID: %d artikel", len(r))
    articles_all.extend(r)

    log.info("  [7/8] Kontan...")
    r = run_kontan_scraper(cfg, url_sudah_ada)
    log.info("  Kontan: %d artikel", len(r))
    articles_all.extend(r)

    log.info("  [8/8] Liputan6 (RSS)...")
    r = run_liputan6_scraper(cfg, url_sudah_ada)
    log.info("  Liputan6: %d artikel", len(r))
    articles_all.extend(r)

    log.info("Total semua sumber: %d artikel baru", len(articles_all))

    if not articles_all:
        log.warning("Tidak ada artikel baru. Scan selesai.")
        html_path = save_html([], cfg, run_time)
        pages_url = publish_to_github(open(html_path, encoding="utf-8").read(), cfg, run_time)
        if pages_url:
            msg = build_message([], cfg, pages_url, run_time)
            send_telegram(cfg, msg)
        print("✓ Tidak ada artikel baru.")
        return

    # ── Step 2: Analisis Claude API ───────────────────────────────
    log.info("STEP 2: Analisis Claude API...")
    results = analyze_articles(articles_all, cfg)

    # ── Step 3: Simpan DB ─────────────────────────────────────────
    log.info("STEP 3: Simpan ke database...")
    simpan_ke_db(results)

    # ── Step 4: Render HTML ───────────────────────────────────────
    log.info("STEP 4: Render HTML...")
    html_path = save_html(results, cfg, run_time)

    # ── Step 5: Upload ke GitHub Pages ────────────────────────────
    log.info("STEP 5: Upload ke GitHub Pages...")
    pages_url = None
    try:
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        pages_url = publish_to_github(html_content, cfg, run_time)
        if pages_url:
            log.info("GitHub Pages: %s", pages_url)
        else:
            log.warning("Upload GitHub Pages gagal.")
    except Exception as e:
        log.error("Error upload GitHub: %s", e)

    # ── Step 6: Notifikasi Telegram ───────────────────────────────
    log.info("STEP 6: Kirim notifikasi Telegram...")
    try:
        tg_url = pages_url or html_path
        msg    = build_message(results, cfg, tg_url, run_time)
        ok     = send_telegram(cfg, msg)
        log.info("Telegram: %s", "OK" if ok else "Gagal")
    except Exception as e:
        log.error("Error Telegram: %s", e)

    # ── Summary ───────────────────────────────────────────────────
    threshold   = cfg["score_threshold"]
    signal_kuat = [r for r in results if r.get("skor", 0) >= threshold["signal_kuat"]]
    radar       = [r for r in results if threshold["radar"] <= r.get("skor", 0) < threshold["signal_kuat"]]
    pantau      = [r for r in results if threshold["pantau"] <= r.get("skor", 0) < threshold["radar"]]

    print("\n" + "=" * 60)
    print(f"  ✓ Market Scan selesai — {len(results)} artikel")
    print(f"  Signal Kuat : {len(signal_kuat)}")
    print(f"  Radar       : {len(radar)}")
    print(f"  Pantau      : {len(pantau)}")
    if pages_url:
        print(f"  GitHub Pages: {pages_url}")
    print("=" * 60 + "\n")

    if signal_kuat:
        print("  🔴 SIGNAL KUAT:")
        for a in signal_kuat:
            src    = a.get("source", "")
            ticker = a.get("ticker", "")
            print(f"     [{a['skor']}] [{src}] {a['judul'][:65]}")
            if ticker:
                print(f"          Ticker: {ticker}")
        print()


if __name__ == "__main__":
    main()
