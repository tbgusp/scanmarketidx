"""
scraper_idxchannel.py
Mengambil artikel dari IDX Channel — kanal Market News, Economics, Banking.
Paginasi per kanal sampai max_articles unik terpenuhi.
"""

import requests
import time
import random
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

BASE_URL = "https://www.idxchannel.com"
SOURCE_LABEL = "IDX"

KANAL_LIST = ["market-news", "economics", "banking"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.idxchannel.com/",
}


def fetch_idxchannel_halaman(kanal: str, page: int, delay_min: float, delay_max: float) -> list[dict]:
    """
    Fetch satu halaman kanal IDX Channel.
    Return: list of { url, judul, tanggal_raw } — kosong jika habis/redirect.
    """
    url = f"{BASE_URL}/{kanal}" if page == 1 else f"{BASE_URL}/{kanal}?page={page}"
    log.info("[IDX] Scraping kanal %s halaman %d → %s", kanal, page, url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        log.error("[IDX] Gagal fetch kanal %s halaman %d: %s", kanal, page, e)
        return []

    # Deteksi redirect ke halaman 1 (berarti sudah tidak ada lagi)
    if page > 1:
        final = resp.url.rstrip("/")
        base  = f"{BASE_URL}/{kanal}"
        if final == base or f"page={page}" not in final:
            log.info("[IDX] Kanal %s halaman %d redirect/habis, berhenti.", kanal, page)
            return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Filter: hanya artikel dari kanal yang kita target
        is_artikel = any(f"/{k}/" in href and len(href) > len(f"/{k}/") for k in KANAL_LIST)
        if not is_artikel:
            continue

        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        full_url = full_url.split("?")[0].rstrip("/")

        if full_url in seen:
            continue
        seen.add(full_url)

        # Ambil judul
        judul = a.get_text(strip=True)
        if len(judul) < 15:
            parent = a.find_parent(["article", "div", "li", "section"])
            if parent:
                h_el = parent.find(["h1", "h2", "h3"])
                if h_el:
                    judul = h_el.get_text(strip=True)

        if len(judul) < 10:
            continue

        # Ambil tanggal
        tgl_raw = ""
        parent = a.find_parent(["article", "div", "li", "section"])
        if parent:
            tgl_el = parent.find("time")
            if tgl_el:
                tgl_raw = tgl_el.get("datetime", "") or tgl_el.get_text(strip=True)

        articles.append({"url": full_url, "judul": judul, "tanggal_raw": tgl_raw})

    log.info("[IDX] Ditemukan %d artikel di kanal %s halaman %d", len(articles), kanal, page)
    return articles


def fetch_idxchannel_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel IDX Channel dan ekstrak konten lengkap.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[IDX] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[IDX] Gagal fetch artikel %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Judul ──
    judul = ""
    for sel in ["h1.detail__title", "h1.article-title", "h1.title", "h1", "meta[property='og:title']"]:
        el = soup.select_one(sel)
        if el:
            judul = el.get("content", "") or el.get_text(strip=True)
            if judul:
                break

    # ── Tanggal ──
    tanggal = ""
    for sel in [
        "meta[property='article:published_time']",
        "time[datetime]", "span.date", "div.date",
        ".article-date", ".publish-date", "time",
    ]:
        el = soup.select_one(sel)
        if el:
            tanggal = el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True)
            if tanggal:
                break

    # ── Penulis ──
    penulis = ""
    for sel in ["meta[name='author']", "span.author", "div.author", "a[rel='author']", ".article-author"]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            if penulis:
                break

    # ── Konten ──
    konten_parts = []
    for sel in [
        "div.detail__body-text", "div.article-content",
        "div.article-body", "div.content-article",
        "div.content-text", "article",
    ]:
        container = soup.select_one(sel)
        if container:
            for tag in container.select("script, style, ins, .ads, .advertisement, figure, .related"):
                tag.decompose()
            paragraphs = container.find_all("p")
            if paragraphs:
                konten_parts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
                if konten_parts:
                    break

    if not konten_parts:
        all_p = soup.find_all("p")
        konten_parts = [p.get_text(strip=True) for p in all_p if len(p.get_text(strip=True)) > 50]

    konten = "\n\n".join(konten_parts)

    if len(konten) < 100:
        log.warning("[IDX] Konten terlalu pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  SOURCE_LABEL,
    }


def run_idxchannel_scraper(config: dict, url_sudah_ada_fn) -> list[dict]:
    """
    Jalankan scraping IDX Channel untuk kanal Market News, Economics, Banking.
    url_sudah_ada_fn: fungsi cek duplikat dari scraper.py
    Return: list artikel baru yang siap dianalisis.
    """
    idx_cfg = config.get("sources", {}).get("idxchannel", {})
    if not idx_cfg.get("enabled", False):
        log.info("[IDX] Dinonaktifkan di config, skip.")
        return []

    max_articles  = idx_cfg.get("max_articles", 30)
    delay_min     = config["scraper"]["request_delay_min"]
    delay_max     = config["scraper"]["request_delay_max"]
    MAX_PAGES     = 5  # safety cap per kanal

    queue     = []
    seen_urls = set()

    for kanal in KANAL_LIST:
        if len(queue) >= max_articles:
            break

        for page in range(1, MAX_PAGES + 1):
            if len(queue) >= max_articles:
                break

            items = fetch_idxchannel_halaman(kanal, page, delay_min, delay_max)
            if not items:
                break

            added = 0
            for item in items:
                if len(queue) >= max_articles:
                    break
                url = item["url"]
                if url not in seen_urls and not url_sudah_ada_fn(url):
                    seen_urls.add(url)
                    queue.append(item)
                    added += 1

            if added == 0:
                log.info("[IDX] Kanal %s halaman %d semua sudah di DB, berhenti.", kanal, page)
                break

    log.info("[IDX] Total artikel baru ditemukan: %d (target: %d)", len(queue), max_articles)
    queue = queue[:max_articles]

    hasil = []
    for item in queue:
        artikel = fetch_idxchannel_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[IDX] Berhasil dibaca: %d artikel", len(hasil))
    return hasil
