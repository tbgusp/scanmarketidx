"""
scraper_idnfinancials.py
Mengambil artikel dari IDN Financials — /id/news dengan pagination /id/news/page/N
"""

import requests
import time
import random
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

BASE_URL     = "https://www.idnfinancials.com"
SOURCE_LABEL = "IDNFinancials"

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
    "Referer":         "https://www.idnfinancials.com/id/",
}


def fetch_idnfinancials_halaman(page: int, delay_min: float, delay_max: float) -> list[dict]:
    """
    Ambil daftar artikel dari satu halaman IDN Financials.
    Halaman 1 = /id/news, halaman N = /id/news/page/N
    Return: list of { url, judul, tanggal_raw, summary }
    """
    url = f"{BASE_URL}/id/news" if page == 1 else f"{BASE_URL}/id/news/page/{page}"
    log.info("[IDNFinancials] Scraping halaman %d → %s", page, url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        log.error("[IDNFinancials] Gagal fetch halaman %d: %s", page, e)
        return []

    # Deteksi redirect ke halaman lain (berarti page N tidak ada)
    if page > 1 and f"/page/{page}" not in resp.url:
        log.info("[IDNFinancials] Halaman %d redirect/habis, berhenti.", page)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    # Selector dari page source: article.item.article > h2.title > a
    for article_el in soup.select("article.item.article"):
        a_tag = article_el.select_one("h2.title > a, h1.title > a")
        if not a_tag or not a_tag.get("href"):
            continue

        href     = a_tag["href"]
        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)

        if full_url in seen:
            continue
        seen.add(full_url)

        judul = a_tag.get_text(strip=True)
        if len(judul) < 10:
            continue

        # Tanggal dari p.date-published
        tgl_raw = ""
        tgl_el  = article_el.select_one("p.date-published")
        if tgl_el:
            tgl_raw = tgl_el.get("data-date", "") or tgl_el.get_text(strip=True)

        # Summary
        summary = ""
        sum_el  = article_el.select_one("p.summary")
        if sum_el:
            summary = sum_el.get_text(strip=True)

        articles.append({
            "url":         full_url,
            "judul":       judul,
            "tanggal_raw": tgl_raw,
            "summary":     summary,
        })

    # Juga ambil dari featured news (div.first dan div.ln-item)
    for a_tag in soup.select("div.first a[href], div.ln-item a[href]"):
        href = a_tag.get("href", "")
        if "/id/news/" not in href:
            continue

        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        judul = a_tag.get("title", "").strip()
        if not judul:
            h_el  = a_tag.find(["h1", "h2"])
            judul = h_el.get_text(strip=True) if h_el else ""

        if len(judul) < 10:
            continue

        tgl_raw = ""
        parent  = a_tag.find_parent(["div"])
        if parent:
            tgl_el  = parent.select_one("p.date-published")
            if tgl_el:
                tgl_raw = tgl_el.get("data-date", "") or tgl_el.get_text(strip=True)

        articles.append({
            "url":         full_url,
            "judul":       judul,
            "tanggal_raw": tgl_raw,
            "summary":     "",
        })

    log.info("[IDNFinancials] Ditemukan %d artikel di halaman %d", len(articles), page)
    return articles


def fetch_idnfinancials_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel IDN Financials dan ekstrak konten.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[IDNFinancials] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[IDNFinancials] Gagal fetch artikel %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Judul ──
    judul = ""
    for sel in ["h1.title", "h1.article-title", "h1", "meta[property='og:title']"]:
        el = soup.select_one(sel)
        if el:
            judul = el.get("content", "") or el.get_text(strip=True)
            if judul:
                break

    # ── Tanggal ──
    tanggal = ""
    for sel in [
        "meta[property='article:published_time']",
        "p.date-published[data-date]",
        "p.date-published",
        "time[datetime]",
        "span.date",
    ]:
        el = soup.select_one(sel)
        if el:
            tanggal = el.get("content", "") or el.get("data-date", "") or el.get("datetime", "") or el.get_text(strip=True)
            if tanggal:
                break

    # ── Penulis ──
    penulis = ""
    for sel in ["meta[name='author']", "span.author", "a.author", ".reporter-name"]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            if penulis:
                break

    # ── Konten ──
    konten_parts = []
    for sel in ["div.article-body", "div.article-content", "div.content", "article"]:
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
        log.warning("[IDNFinancials] Konten pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  SOURCE_LABEL,
    }


def run_idnfinancials_scraper(config: dict, url_sudah_ada_fn) -> list[dict]:
    """
    Jalankan scraping IDN Financials.
    url_sudah_ada_fn: fungsi cek duplikat dari scraper.py
    Return: list artikel baru yang siap dianalisis.
    """
    cfg = config.get("sources", {}).get("idnfinancials", {})
    if not cfg.get("enabled", False):
        log.info("[IDNFinancials] Dinonaktifkan di config, skip.")
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

        items = fetch_idnfinancials_halaman(page, delay_min, delay_max)
        if not items:
            log.info("[IDNFinancials] Halaman %d kosong, berhenti.", page)
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
            log.info("[IDNFinancials] Halaman %d semua sudah di DB, berhenti.", page)
            break

    log.info("[IDNFinancials] Total artikel baru: %d (target: %d)", len(queue), max_articles)
    queue = queue[:max_articles]

    hasil = []
    for item in queue:
        artikel = fetch_idnfinancials_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[IDNFinancials] Berhasil dibaca: %d artikel", len(hasil))
    return hasil
