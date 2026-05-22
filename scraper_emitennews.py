"""
scraper_emitennews.py
Mengambil artikel dari Emitennews.com — /home/updates dengan pagination /home/updates/N
Pattern pagination: page 1 = /home/updates, page 2 = /home/updates/9, page 3 = /home/updates/18
(increment 9 per halaman)
"""

import requests
import time
import random
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

BASE_URL     = "https://emitennews.com"
SOURCE_LABEL = "EmitenNews"

# Pagination: offset naik 9 per halaman
# page 1 = /home/updates
# page 2 = /home/updates/9
# page 3 = /home/updates/18  dst
PAGE_OFFSET  = 9

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         "https://emitennews.com/",
}


def _url_untuk_page(page: int) -> str:
    """Hitung URL halaman berdasarkan nomor halaman (1-based)."""
    if page == 1:
        return f"{BASE_URL}/home/updates"
    offset = (page - 1) * PAGE_OFFSET
    return f"{BASE_URL}/home/updates/{offset}"


def fetch_emitennews_halaman(page: int, delay_min: float, delay_max: float) -> list[dict]:
    """
    Ambil daftar artikel dari satu halaman Emitennews.
    Return: list of { url, judul, tanggal_raw }
    """
    url = _url_untuk_page(page)
    log.info("[EmitenNews] Scraping halaman %d → %s", page, url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        log.error("[EmitenNews] Gagal fetch halaman %d: %s", page, e)
        return []

    # Deteksi redirect ke halaman 1 (berarti offset tidak ada)
    if page > 1:
        final = resp.url.rstrip("/")
        base  = f"{BASE_URL}/home/updates"
        if final == base:
            log.info("[EmitenNews] Halaman %d redirect ke halaman 1, berhenti.", page)
            return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    # Artikel ada di a[href*="/news/"] — dari page source terlihat jelas
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/news/" not in href:
            continue

        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        full_url = full_url.split("?")[0].rstrip("/")

        if full_url in seen:
            continue
        seen.add(full_url)

        # Ambil judul dari text anchor atau heading terdekat
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
        parent  = a.find_parent(["article", "div", "li", "section"])
        if parent:
            tgl_el = parent.find("time")
            if not tgl_el:
                # Coba cari span/div dengan kata "ago", "jam", "hari", tanggal
                tgl_el = parent.find(
                    attrs={"class": lambda c: c and any(
                        k in str(c).lower() for k in ["date", "time", "published", "ago"]
                    )}
                )
            if tgl_el:
                tgl_raw = tgl_el.get("datetime", "") or tgl_el.get_text(strip=True)

        articles.append({
            "url":         full_url,
            "judul":       judul,
            "tanggal_raw": tgl_raw,
        })

    log.info("[EmitenNews] Ditemukan %d artikel di halaman %d", len(articles), page)
    return articles


def fetch_emitennews_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel Emitennews dan ekstrak konten.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[EmitenNews] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[EmitenNews] Gagal fetch artikel %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Judul ──
    judul = ""
    for sel in ["h1.title", "h1.news-title", "h1", "meta[property='og:title']"]:
        el = soup.select_one(sel)
        if el:
            judul = el.get("content", "") or el.get_text(strip=True)
            if judul:
                break

    # ── Tanggal ──
    tanggal = ""
    for sel in [
        "meta[property='article:published_time']",
        "time[datetime]",
        "span.date", "div.date", ".publish-date", ".news-date",
        "time",
    ]:
        el = soup.select_one(sel)
        if el:
            tanggal = el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True)
            if tanggal:
                break

    # ── Penulis ──
    penulis = ""
    for sel in ["meta[name='author']", "span.author", ".reporter", ".byline", "a[rel='author']"]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            if penulis:
                break

    # ── Konten ──
    konten_parts = []
    for sel in [
        "div.news-content", "div.article-content",
        "div.content-body", "div.post-content",
        "div.detail-content", "article",
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
        log.warning("[EmitenNews] Konten pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  SOURCE_LABEL,
    }


def run_emitennews_scraper(config: dict, url_sudah_ada_fn) -> list[dict]:
    """
    Jalankan scraping Emitennews.
    url_sudah_ada_fn: fungsi cek duplikat dari scraper.py
    Return: list artikel baru yang siap dianalisis.
    """
    cfg = config.get("sources", {}).get("emitennews", {})
    if not cfg.get("enabled", False):
        log.info("[EmitenNews] Dinonaktifkan di config, skip.")
        return []

    max_articles = cfg.get("max_articles", 30)
    delay_min    = config["scraper"]["request_delay_min"]
    delay_max    = config["scraper"]["request_delay_max"]
    MAX_PAGES    = 10  # safety cap

    queue     = []
    seen_urls = set()

    for page in range(1, MAX_PAGES + 1):
        if len(queue) >= max_articles:
            break

        items = fetch_emitennews_halaman(page, delay_min, delay_max)
        if not items:
            log.info("[EmitenNews] Halaman %d kosong/redirect, berhenti.", page)
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
            log.info("[EmitenNews] Halaman %d semua sudah di DB, berhenti.", page)
            break

    log.info("[EmitenNews] Total artikel baru: %d (target: %d)", len(queue), max_articles)
    queue = queue[:max_articles]

    hasil = []
    for item in queue:
        artikel = fetch_emitennews_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[EmitenNews] Berhasil dibaca: %d artikel", len(hasil))
    return hasil
