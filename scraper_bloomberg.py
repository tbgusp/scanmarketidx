"""
scraper_bloomberg.py
Mengambil artikel dari Bloomberg Technoz — kanal Market, per tanggal.
URL pattern: https://www.bloombergtechnoz.com/indeks/market/YYYY-MM-DD
"""

import requests
import time
import random
import logging
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin

log = logging.getLogger(__name__)

BASE_URL = "https://www.bloombergtechnoz.com"
SOURCE_LABEL = "Bloomberg"

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
    "Referer": "https://www.bloombergtechnoz.com/",
}


def fetch_bloomberg_indeks(tanggal_str: str, delay_min: float, delay_max: float) -> list[dict]:
    """
    Ambil daftar URL artikel dari halaman indeks Bloomberg tanggal tertentu.
    tanggal_str format: "YYYY-MM-DD"
    Return: list of { url, judul, tanggal_raw }
    """
    url = f"{BASE_URL}/indeks/market/{tanggal_str}"
    log.info("[Bloomberg] Scraping tanggal %s → %s", tanggal_str, url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[Bloomberg] Gagal fetch indeks %s: %s", tanggal_str, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/detail-news/" not in href:
            continue

        full_url = href if href.startswith("http") else urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)

        # Ambil judul dari title attribute atau text, atau dari heading terdekat
        judul = a.get("title", "").strip() or a.get_text(strip=True)
        if len(judul) < 15:
            parent = a.find_parent(["article", "div", "li"])
            if parent:
                h_el = parent.find(["h1", "h2", "h3", "h4"])
                if h_el:
                    judul = h_el.get_text(strip=True)

        if len(judul) < 10:
            continue

        # Ambil tanggal dari elemen terdekat
        tgl_raw = ""
        parent = a.find_parent(["article", "div", "li"])
        if parent:
            tgl_el = parent.find("time")
            if tgl_el:
                tgl_raw = tgl_el.get("datetime", "") or tgl_el.get_text(strip=True)

        articles.append({
            "url":         full_url,
            "judul":       judul,
            "tanggal_raw": tgl_raw or tanggal_str,
        })

    log.info("[Bloomberg] Ditemukan %d artikel di tanggal %s", len(articles), tanggal_str)
    return articles


def fetch_bloomberg_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel Bloomberg dan ekstrak konten lengkap.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[Bloomberg] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[Bloomberg] Gagal fetch artikel %s: %s", url, e)
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
        "time[datetime]", "span.published-date",
        "div.article-date", ".detail__date", "time", "span.date",
    ]:
        el = soup.select_one(sel)
        if el:
            tanggal = el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True)
            if tanggal:
                break

    # ── Penulis ──
    penulis = ""
    for sel in [
        "meta[name='author']", "span.author-name",
        "div.article-author", "a[rel='author']",
        ".detail__author", "span.author",
    ]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            if penulis:
                break

    # ── Konten ──
    konten_parts = []
    for sel in [
        "div.detail__body-text", "div.article-body",
        "div.detail-content", "div.content-text", "article",
    ]:
        container = soup.select_one(sel)
        if container:
            for tag in container.select("script, style, ins, .ads, .advertisement, figure, .related-articles"):
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
        log.warning("[Bloomberg] Konten terlalu pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  SOURCE_LABEL,
    }


def run_bloomberg_scraper(config: dict, url_sudah_ada_fn) -> list[dict]:
    """
    Jalankan scraping Bloomberg untuk N hari ke belakang.
    url_sudah_ada_fn: fungsi cek duplikat dari scraper.py
    Return: list artikel baru yang siap dianalisis.
    """
    bloomberg_cfg = config.get("sources", {}).get("bloomberg", {})
    if not bloomberg_cfg.get("enabled", False):
        log.info("[Bloomberg] Dinonaktifkan di config, skip.")
        return []

    days_back    = bloomberg_cfg.get("days_back", 3)
    max_articles = bloomberg_cfg.get("max_articles", 30)
    delay_min    = config["scraper"]["request_delay_min"]
    delay_max    = config["scraper"]["request_delay_max"]

    today        = datetime.now().date()
    tanggal_list = [
        (today - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(days_back)
    ]

    queue     = []
    seen_urls = set()

    for tgl_str in tanggal_list:
        if len(queue) >= max_articles:
            break
        items = fetch_bloomberg_indeks(tgl_str, delay_min, delay_max)
        for item in items:
            if len(queue) >= max_articles:
                break
            url = item["url"]
            if url not in seen_urls and not url_sudah_ada_fn(url):
                seen_urls.add(url)
                queue.append(item)

    log.info("[Bloomberg] Total artikel baru ditemukan: %d (max: %d)", len(queue), max_articles)

    hasil = []
    for item in queue:
        artikel = fetch_bloomberg_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[Bloomberg] Berhasil dibaca: %d artikel", len(hasil))
    return hasil
