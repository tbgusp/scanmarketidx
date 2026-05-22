"""
scraper_kontan.py
Mengambil artikel dari Kontan.co.id — halaman indeks per tanggal
Metode: days_back — ambil artikel dari N hari ke belakang

URL pola indeks per tanggal:
  https://www.kontan.co.id/search/indeks?kanal=&tanggal={DD}&bulan={MM}&tahun={YYYY}&pos=indeks&per_page={OFFSET}

Pagination: per_page naik 20 per halaman (offset 0, 20, 40, 60, ...)
"""

import requests
import time
import random
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

BASE_URL     = "https://www.kontan.co.id"
SOURCE_LABEL = "Kontan"
PAGE_SIZE    = 20   # Kontan menampilkan 20 artikel per offset
MAX_PAGES    = 10   # safety cap per tanggal

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
    "Referer":         "https://www.kontan.co.id/",
}


def _indeks_url(tanggal: datetime, offset: int) -> str:
    """Bangun URL indeks Kontan untuk tanggal dan offset tertentu."""
    return (
        f"{BASE_URL}/search/indeks"
        f"?kanal=&tanggal={tanggal.day}"
        f"&bulan={tanggal.month:02d}"
        f"&tahun={tanggal.year}"
        f"&pos=indeks&per_page={offset}"
    )


def fetch_kontan_halaman(tanggal: datetime, offset: int,
                          delay_min: float, delay_max: float) -> list[dict]:
    """
    Ambil daftar artikel dari satu halaman indeks Kontan.
    Return: list of { url, judul, tanggal_raw }
    """
    url = _indeks_url(tanggal, offset)
    tgl_str = tanggal.strftime("%Y-%m-%d")
    log.info("[Kontan] Scraping %s offset %d → %s", tgl_str, offset, url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[Kontan] Gagal fetch %s offset %d: %s", tgl_str, offset, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    # Artikel Kontan: href="https://*.kontan.co.id/news/..."
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/news/" not in href or "kontan.co.id" not in href:
            continue
        if "asset.kontan" in href or "foto.kontan" in href:
            continue

        full_url = href.rstrip("/")
        if full_url in seen:
            continue
        seen.add(full_url)

        # Ambil judul dari heading terdekat
        judul = a.get_text(strip=True)
        if len(judul) < 15:
            parent = a.find_parent(["li", "div", "article"])
            if parent:
                h_el = parent.find(["h1", "h2", "h3"])
                if h_el:
                    judul = h_el.get_text(strip=True)

        if len(judul) < 10:
            continue

        # Tanggal dari elemen terdekat
        tgl_raw = tgl_str
        parent = a.find_parent(["li", "div", "article"])
        if parent:
            tgl_el = parent.find("time")
            if not tgl_el:
                span = parent.find("span", class_=lambda c: c and "gray" in str(c).lower())
                if span:
                    tgl_el = span
            if tgl_el:
                tgl_raw = tgl_el.get("datetime", "") or tgl_el.get_text(strip=True) or tgl_str

        articles.append({
            "url":         full_url,
            "judul":       judul,
            "tanggal_raw": tgl_raw,
        })

    log.info("[Kontan] Ditemukan %d artikel di %s offset %d", len(articles), tgl_str, offset)
    return articles


def fetch_kontan_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel Kontan dan ekstrak konten.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[Kontan] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[Kontan] Gagal fetch artikel %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Judul ──
    judul = ""
    for sel in ["h1.detail-title", "h1.title", "h1",
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
        "span.font-gray", "div.date", ".publish-date",
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
                ".byline", "a[rel='author']"]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            if penulis:
                break

    # ── Konten ──
    konten_parts = []
    for sel in [
        "div.detail-content", "div.article-body", "div.content-detail",
        "div.isi-konten", "div.isi", "article",
    ]:
        container = soup.select_one(sel)
        if container:
            for tag in container.select(
                "script, style, ins, .ads, .advertisement, figure, .related, .tags, .baca-juga"
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
        log.warning("[Kontan] Konten pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  SOURCE_LABEL,
    }


def run_kontan_scraper(config: dict, url_sudah_ada_fn) -> list[dict]:
    """
    Jalankan scraping Kontan untuk N hari ke belakang.
    url_sudah_ada_fn: fungsi cek duplikat dari scraper.py
    Return: list artikel baru yang siap dianalisis.
    """
    cfg = config.get("sources", {}).get("kontan", {})
    if not cfg.get("enabled", False):
        log.info("[Kontan] Dinonaktifkan di config, skip.")
        return []

    days_back    = cfg.get("days_back", 3)
    max_articles = cfg.get("max_articles", 30)
    delay_min    = config["scraper"]["request_delay_min"]
    delay_max    = config["scraper"]["request_delay_max"]

    today        = datetime.now()
    tanggal_list = [today - timedelta(days=i) for i in range(days_back)]

    queue     = []
    seen_urls = set()

    for tgl in tanggal_list:
        if len(queue) >= max_articles:
            break
        for page_num in range(MAX_PAGES):
            if len(queue) >= max_articles:
                break
            offset = page_num * PAGE_SIZE
            items = fetch_kontan_halaman(tgl, offset, delay_min, delay_max)

            if not items:
                log.info("[Kontan] Halaman kosong di %s offset %d, berhenti.",
                         tgl.strftime("%Y-%m-%d"), offset)
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
                log.info("[Kontan] Semua artikel di %s offset %d sudah di DB.",
                         tgl.strftime("%Y-%m-%d"), offset)
                break

    log.info("[Kontan] Total artikel baru ditemukan: %d (max: %d)", len(queue), max_articles)

    hasil = []
    for item in queue:
        artikel = fetch_kontan_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[Kontan] Berhasil dibaca: %d artikel", len(hasil))
    return hasil
