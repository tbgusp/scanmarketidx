"""
scraper_cnbc.py  (versi RSS — menggantikan scraper.py lama)
Mengambil artikel dari CNBC Indonesia — kanal Market via RSS Feed
Metode: days_back — filter artikel dari RSS berdasarkan tanggal publikasi

RSS Feed: https://www.cnbcindonesia.com/market/rss/
RSS tidak kena blokir Cloudflare — aman dijalankan dari cloud server.
"""

import requests
import time
import random
import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

log = logging.getLogger(__name__)

SOURCE_LABEL    = "CNBC"
DEFAULT_RSS_URL = "https://www.cnbcindonesia.com/market/rss/"

HEADERS_RSS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         "https://www.cnbcindonesia.com/",
}

HEADERS_HTML = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         "https://www.cnbcindonesia.com/",
}


def _parse_rss_date(date_str: str) -> datetime | None:
    """Parse tanggal RSS (RFC 2822) ke datetime aware UTC."""
    if not date_str:
        return None
    try:
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def fetch_cnbc_rss(rss_url: str, days_back: int,
                   delay_min: float, delay_max: float) -> list[dict]:
    """
    Ambil artikel dari RSS CNBC Indonesia, filter berdasarkan days_back.
    Return: list of { url, judul, tanggal_raw }
    """
    log.info("[CNBC] Fetching RSS → %s", rss_url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(rss_url, headers=HEADERS_RSS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[CNBC] Gagal fetch RSS: %s", e)
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        log.error("[CNBC] Gagal parse RSS XML: %s", e)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

    articles = []
    seen = set()

    channel = root.find("channel")
    if channel is None:
        log.warning("[CNBC] Tidak ditemukan <channel> dalam RSS.")
        return []

    for item in channel.findall("item"):
        link_el  = item.find("link")
        title_el = item.find("title")
        date_el  = item.find("pubDate")

        if link_el is None or title_el is None:
            continue

        url    = (link_el.text or "").strip()
        judul  = (title_el.text or "").strip()
        tgl_raw = (date_el.text or "").strip() if date_el is not None else ""

        if not url or len(judul) < 10:
            continue
        if url in seen:
            continue
        seen.add(url)

        if tgl_raw:
            pub_dt = _parse_rss_date(tgl_raw)
            if pub_dt and pub_dt < cutoff:
                log.debug("[CNBC] Skip artikel lama: %s | %s", tgl_raw, judul[:50])
                continue

        articles.append({
            "url":         url,
            "judul":       judul,
            "tanggal_raw": tgl_raw,
        })

    log.info("[CNBC] Ditemukan %d artikel dari RSS (dalam %d hari)", len(articles), days_back)
    return articles


def fetch_cnbc_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel CNBC dan ekstrak konten.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[CNBC] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS_HTML, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[CNBC] Gagal fetch artikel %s: %s", url, e)
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
        "time[datetime]", "div.date", "span.date",
        ".detail__date", "time",
    ]:
        el = soup.select_one(sel)
        if el:
            tanggal = el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True)
            if tanggal:
                break

    # ── Penulis ──
    penulis = ""
    for sel in ["meta[name='author']", "span.author",
                ".detail__author", "a[rel='author']", ".byline"]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            if penulis:
                break

    # ── Konten ──
    konten_parts = []
    for sel in [
        "div.detail-text", "div.detail__body-text",
        "div.article-content", "div.content-detail", "article",
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
        log.warning("[CNBC] Konten pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  SOURCE_LABEL,
    }


def run_cnbc_rss_scraper(config: dict, url_sudah_ada_fn) -> list[dict]:
    """
    Jalankan scraping CNBC Indonesia via RSS untuk N hari ke belakang.
    url_sudah_ada_fn: fungsi cek duplikat dari scraper.py
    Return: list artikel baru yang siap dianalisis.
    """
    cfg = config.get("sources", {}).get("cnbc", {})
    if not cfg.get("enabled", False):
        log.info("[CNBC] Dinonaktifkan di config, skip.")
        return []

    rss_url      = cfg.get("rss_url", DEFAULT_RSS_URL)
    days_back    = cfg.get("days_back", 3)
    max_articles = cfg.get("max_articles", 30)
    delay_min    = config["scraper"]["request_delay_min"]
    delay_max    = config["scraper"]["request_delay_max"]

    items     = fetch_cnbc_rss(rss_url, days_back, delay_min, delay_max)
    queue     = []
    seen_urls = set()

    for item in items:
        if len(queue) >= max_articles:
            break
        url = item["url"]
        if url not in seen_urls and not url_sudah_ada_fn(url):
            seen_urls.add(url)
            queue.append(item)

    log.info("[CNBC] Total artikel baru: %d (max: %d)", len(queue), max_articles)

    hasil = []
    for item in queue:
        artikel = fetch_cnbc_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[CNBC] Berhasil dibaca: %d artikel", len(hasil))
    return hasil
