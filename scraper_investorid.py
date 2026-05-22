"""
scraper_investorid.py
Mengambil artikel dari Investor.ID — kanal /market
Metode: max_articles dari halaman indeks
URL indeks: https://investor.id/market
URL artikel: https://investor.id/market/{ID}/{slug}
"""

import requests
import time
import random
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

BASE_URL     = "https://investor.id"
SOURCE_LABEL = "InvestorID"

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
    "Referer":         "https://investor.id/",
}


def fetch_investorid_indeks(source_url: str, delay_min: float, delay_max: float) -> list[dict]:
    """
    Ambil daftar artikel dari halaman indeks Investor.ID.
    Return: list of { url, judul, tanggal_raw }
    """
    log.info("[InvestorID] Scraping indeks → %s", source_url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(source_url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[InvestorID] Gagal fetch indeks: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    # Artikel di Investor ID: href="/market/{ID}/{slug}"
    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Filter hanya URL artikel market (ada ID numerik)
        import re
        if not re.match(r"^/market/\d+/", href):
            continue

        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        # Ambil judul dari heading terdekat atau teks anchor
        judul = a.get_text(strip=True)
        if len(judul) < 15:
            parent = a.find_parent(["article", "div", "li", "section"])
            if parent:
                h_el = parent.find(["h1", "h2", "h3", "h4"])
                if h_el:
                    judul = h_el.get_text(strip=True)

        if len(judul) < 10:
            continue

        # Ambil tanggal dari elemen terdekat
        tgl_raw = ""
        parent = a.find_parent(["article", "div", "li", "section"])
        if parent:
            tgl_el = parent.find("time")
            if not tgl_el:
                tgl_el = parent.find(attrs={"class": lambda c: c and any(
                    k in str(c).lower() for k in ["date", "time", "published", "ago"]
                )})
            if tgl_el:
                tgl_raw = tgl_el.get("datetime", "") or tgl_el.get_text(strip=True)

        articles.append({
            "url":         full_url,
            "judul":       judul,
            "tanggal_raw": tgl_raw,
        })

    log.info("[InvestorID] Ditemukan %d artikel di indeks", len(articles))
    return articles


def fetch_investorid_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel Investor.ID dan ekstrak konten.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[InvestorID] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[InvestorID] Gagal fetch artikel %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Judul ──
    judul = ""
    for sel in ["h1.detail-title", "h1.post-title", "h1.title", "h1",
                "meta[property='og:title']"]:
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
        "span.date", "div.date", ".publish-date", ".post-date",
        "time",
    ]:
        el = soup.select_one(sel)
        if el:
            tanggal = el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True)
            if tanggal:
                break

    # ── Penulis ──
    penulis = ""
    for sel in ["meta[name='author']", "span.author", ".reporter",
                ".byline", "a[rel='author']", ".post-author"]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            if penulis:
                break

    # ── Konten ──
    konten_parts = []
    for sel in [
        "div.detail-content", "div.post-content", "div.article-content",
        "div.content-detail", "div.news-content", "article",
    ]:
        container = soup.select_one(sel)
        if container:
            for tag in container.select(
                "script, style, ins, .ads, .advertisement, figure, .related, .tags"
            ):
                tag.decompose()
            paragraphs = container.find_all("p")
            if paragraphs:
                konten_parts = [
                    p.get_text(strip=True)
                    for p in paragraphs
                    if len(p.get_text(strip=True)) > 30
                ]
                if konten_parts:
                    break

    if not konten_parts:
        all_p = soup.find_all("p")
        konten_parts = [p.get_text(strip=True) for p in all_p if len(p.get_text(strip=True)) > 50]

    konten = "\n\n".join(konten_parts)

    if len(konten) < 100:
        log.warning("[InvestorID] Konten pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  SOURCE_LABEL,
    }


def run_investorid_scraper(config: dict, url_sudah_ada_fn) -> list[dict]:
    """
    Jalankan scraping Investor.ID dengan metode max_articles.
    url_sudah_ada_fn: fungsi cek duplikat dari scraper.py
    Return: list artikel baru yang siap dianalisis.
    """
    cfg = config.get("sources", {}).get("investorid", {})
    if not cfg.get("enabled", False):
        log.info("[InvestorID] Dinonaktifkan di config, skip.")
        return []

    source_url   = cfg.get("source_url", "https://investor.id/market")
    max_articles = cfg.get("max_articles", 30)
    delay_min    = config["scraper"]["request_delay_min"]
    delay_max    = config["scraper"]["request_delay_max"]

    items     = fetch_investorid_indeks(source_url, delay_min, delay_max)
    queue     = []
    seen_urls = set()

    for item in items:
        if len(queue) >= max_articles:
            break
        url = item["url"]
        if url not in seen_urls and not url_sudah_ada_fn(url):
            seen_urls.add(url)
            queue.append(item)

    log.info("[InvestorID] Total artikel baru: %d (target: %d)", len(queue), max_articles)

    hasil = []
    for item in queue:
        artikel = fetch_investorid_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[InvestorID] Berhasil dibaca: %d artikel", len(hasil))
    return hasil
