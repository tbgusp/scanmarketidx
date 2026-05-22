"""
main.py
Orkestrator utama — scraping CNBC + Bloomberg + IDX Channel, analisis, render HTML.
Dipanggil oleh Windows Task Scheduler setiap jam 06:00 dan 18:00.
"""

import json
import logging
import os
import sys
from datetime import datetime

# ── Path setup ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "scraper.log")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger(__name__)


def load_config() -> dict:
    cfg_path = os.path.join(BASE_DIR, "config.json")
    if not os.path.exists(cfg_path):
        log.error("config.json tidak ditemukan di: %s", cfg_path)
        sys.exit(1)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    if not cfg.get("anthropic_api_key") or cfg["anthropic_api_key"] == "MASUKKAN_API_KEY_ANDA_DISINI":
        log.error("API key belum diisi di config.json!")
        print("\n" + "="*60)
        print("  ERROR: Anthropic API key belum diisi!")
        print("  Buka config.json dan isi field 'anthropic_api_key'")
        print("  Contoh: sk-ant-api03-xxxxxxxxxxxx")
        print("="*60 + "\n")
        sys.exit(1)

    return cfg


def simpan_ke_db(articles_with_scores: list):
    """Simpan semua hasil ke SQLite."""
    from scraper import simpan_artikel
    for artikel in articles_with_scores:
        simpan_artikel(artikel)
    log.info("Disimpan %d artikel ke database.", len(articles_with_scores))


def main():
    run_time = datetime.now().isoformat()
    log.info("=" * 60)
    log.info("Market Scan dimulai: %s", run_time)
    log.info("=" * 60)

    # ── Load config ──────────────────────────────────────────────
    cfg = load_config()
    log.info("Config berhasil dimuat.")

    # ── Import semua modul ───────────────────────────────────────
    try:
        from scraper               import run_scraper, init_db, url_sudah_ada
        from scraper_bloomberg     import run_bloomberg_scraper
        from scraper_idxchannel    import run_idxchannel_scraper
        from scraper_idnfinancials import run_idnfinancials_scraper
        from scraper_emitennews    import run_emitennews_scraper
        from scraper_investorid    import run_investorid_scraper
        from scraper_kontan        import run_kontan_scraper
        from scraper_liputan6      import run_liputan6_scraper
        from analyzer              import analyze_articles
        from renderer              import save_html
        from publisher_github      import publish_to_github
        from notifier_telegram     import build_message, send_telegram
    except ImportError as e:
        log.error("Import error: %s", e)
        log.error(
            "Pastikan semua file ada di folder yang sama:\n"
            "  scraper.py, scraper_bloomberg.py, scraper_idxchannel.py,\n"
            "  scraper_investorid.py, scraper_kontan.py, scraper_liputan6.py,\n"
            "  analyzer.py, renderer.py, main.py, config.json"
        )
        sys.exit(1)

    # ── Init database ────────────────────────────────────────────
    init_db()

    # ── Step 1: Scraping semua sumber ───────────────────────────
    log.info("STEP 1: Scraping semua sumber berita...")
    articles_all = []

    log.info("  [1/8] CNBC Indonesia...")
    articles_cnbc = run_scraper(cfg)
    log.info("  CNBC: %d artikel baru", len(articles_cnbc))
    articles_all.extend(articles_cnbc)

    log.info("  [2/8] Bloomberg Technoz...")
    articles_bloomberg = run_bloomberg_scraper(cfg, url_sudah_ada)
    log.info("  Bloomberg: %d artikel baru", len(articles_bloomberg))
    articles_all.extend(articles_bloomberg)

    log.info("  [3/8] IDX Channel...")
    articles_idx = run_idxchannel_scraper(cfg, url_sudah_ada)
    log.info("  IDX Channel: %d artikel baru", len(articles_idx))
    articles_all.extend(articles_idx)

    log.info("  [4/8] IDN Financials...")
    articles_idn = run_idnfinancials_scraper(cfg, url_sudah_ada)
    log.info("  IDN Financials: %d artikel baru", len(articles_idn))
    articles_all.extend(articles_idn)

    log.info("  [5/8] Emiten News...")
    articles_emiten = run_emitennews_scraper(cfg, url_sudah_ada)
    log.info("  Emiten News: %d artikel baru", len(articles_emiten))
    articles_all.extend(articles_emiten)

    log.info("  [6/8] Investor.ID...")
    articles_investorid = run_investorid_scraper(cfg, url_sudah_ada)
    log.info("  Investor.ID: %d artikel baru", len(articles_investorid))
    articles_all.extend(articles_investorid)

    log.info("  [7/8] Kontan...")
    articles_kontan = run_kontan_scraper(cfg, url_sudah_ada)
    log.info("  Kontan: %d artikel baru", len(articles_kontan))
    articles_all.extend(articles_kontan)

    log.info("  [8/8] Liputan6...")
    articles_liputan6 = run_liputan6_scraper(cfg, url_sudah_ada)
    log.info("  Liputan6: %d artikel baru", len(articles_liputan6))
    articles_all.extend(articles_liputan6)

    articles = articles_all
    log.info("Total gabungan semua sumber: %d artikel baru", len(articles))

    if not articles:
        log.warning("Tidak ada artikel baru dari semua sumber. Membuat HTML kosong...")
        html_path = save_html([], cfg, run_time)
        log.info("HTML kosong disimpan: %s", html_path)
        print(f"\n✓ Run selesai. Tidak ada artikel baru. Output: {html_path}")
        return

    # ── Step 2: Analisis dengan Claude API ───────────────────────
    log.info("STEP 2: Analisis dengan Claude API (Haiku screening + Sonnet deep)...")
    results = analyze_articles(articles, cfg)

    # ── Step 3: Simpan ke database ───────────────────────────────
    log.info("STEP 3: Simpan ke database...")
    simpan_ke_db(results)

    # ── Step 4: Render HTML ──────────────────────────────────────
    log.info("STEP 4: Render HTML output...")
    html_path = save_html(results, cfg, run_time)

    # ── Step 5: Publish ke GitHub Pages ──────────────────────────
    log.info("STEP 5: Upload HTML ke GitHub Pages...")
    pages_url = None
    try:
        with open(html_path, encoding="utf-8") as f:
            html_content = f.read()
        pages_url = publish_to_github(html_content, cfg, run_time)
        if pages_url:
            log.info("GitHub Pages URL: %s", pages_url)
        else:
            log.warning("Publish ke GitHub Pages gagal atau token belum diisi.")
    except Exception as e:
        log.error("Error publish ke GitHub: %s", e)

    # ── Step 6: Kirim notifikasi ke Telegram Channel ─────────────
    log.info("STEP 6: Kirim notifikasi Telegram...")
    try:
        tg_url = pages_url or html_path  # fallback ke path lokal kalau upload gagal
        msg = build_message(results, cfg, tg_url, run_time)
        sent = send_telegram(cfg, msg)
        if sent:
            log.info("Notifikasi Telegram berhasil dikirim.")
        else:
            log.warning("Notifikasi Telegram gagal atau belum dikonfigurasi.")
    except Exception as e:
        log.error("Error kirim Telegram: %s", e)

    # ── Summary ──────────────────────────────────────────────────
    threshold   = cfg["score_threshold"]
    signal_kuat = [r for r in results if r.get("skor", 0) >= threshold["signal_kuat"]]
    radar       = [r for r in results if threshold["radar"] <= r.get("skor", 0) < threshold["signal_kuat"]]
    pantau      = [r for r in results if threshold["pantau"] <= r.get("skor", 0) < threshold["radar"]]

    n_cnbc        = len([r for r in results if r.get("source", "CNBC") == "CNBC"])
    n_bloomberg   = len([r for r in results if r.get("source") == "Bloomberg"])
    n_idx         = len([r for r in results if r.get("source") == "IDX"])
    n_idn         = len([r for r in results if r.get("source") == "IDNFinancials"])
    n_emiten      = len([r for r in results if r.get("source") == "EmitenNews"])
    n_investorid  = len([r for r in results if r.get("source") == "InvestorID"])
    n_kontan      = len([r for r in results if r.get("source") == "Kontan"])
    n_liputan6    = len([r for r in results if r.get("source") == "Liputan6"])

    log.info("=" * 60)
    log.info("RUN SELESAI")
    log.info("  Total artikel      : %d", len(results))
    log.info("    CNBC             : %d", n_cnbc)
    log.info("    Bloomberg        : %d", n_bloomberg)
    log.info("    IDX Channel      : %d", n_idx)
    log.info("    IDN Financials   : %d", n_idn)
    log.info("    Emiten News      : %d", n_emiten)
    log.info("    Investor.ID      : %d", n_investorid)
    log.info("    Kontan           : %d", n_kontan)
    log.info("    Liputan6         : %d", n_liputan6)
    log.info("  Signal Kuat (≥%d)  : %d", threshold["signal_kuat"], len(signal_kuat))
    log.info("  Radar (%d-%d)       : %d", threshold["radar"], threshold["signal_kuat"]-1, len(radar))
    log.info("  Pantau (%d-%d)      : %d", threshold["pantau"], threshold["radar"]-1, len(pantau))
    log.info("  Output HTML        : %s", html_path)
    log.info("=" * 60)

    print("\n" + "="*60)
    print(f"  ✓ Market Scan selesai")
    print(f"  Total artikel  : {len(results)}")
    print(f"    CNBC         : {n_cnbc}")
    print(f"    Bloomberg    : {n_bloomberg}")
    print(f"    IDX Channel  : {n_idx}")
    print(f"    IDN Financials: {n_idn}")
    print(f"    Emiten News  : {n_emiten}")
    print(f"    Investor.ID  : {n_investorid}")
    print(f"    Kontan       : {n_kontan}")
    print(f"    Liputan6     : {n_liputan6}")
    print(f"  Signal Kuat    : {len(signal_kuat)}")
    print(f"  Radar          : {len(radar)}")
    print(f"  Pantau         : {len(pantau)}")
    print(f"  Output         : {html_path}")
    if pages_url:
        print(f"  GitHub Pages   : {pages_url}")
    print("="*60 + "\n")

    if signal_kuat:
        print("  🔴 SIGNAL KUAT:")
        for a in signal_kuat:
            src = a.get("source", "CNBC")
            print(f"     [{a['skor']}] [{src}] {a['judul'][:65]}")
            if a.get("ticker"):
                print(f"          Ticker: {a['ticker']}")
        print()


if __name__ == "__main__":
    main()
