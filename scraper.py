"""
scraper.py
Mengambil artikel dari CNBC Indonesia Market /market/indeks/5
"""

import requests
import sqlite3
import json
import time
import random
import logging
import os
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ── Path setup ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "db", "articles.db")
LOG_PATH = os.path.join(BASE_DIR, "scraper.log")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── Headers supaya tidak kena block ─────────────────────────────────────────
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
    "Referer": "https://www.cnbcindonesia.com/",
}

# ── DB setup ─────────────────────────────────────────────────────────────────
def init_db():
    os.makedirs(os.path.join(BASE_DIR, "db"), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT    UNIQUE NOT NULL,
            judul       TEXT,
            tanggal     TEXT,
            penulis     TEXT,
            konten      TEXT,
            ticker      TEXT,
            skor        INTEGER DEFAULT 0,
            breakdown   TEXT,
            verdict     TEXT,
            highlight   TEXT,
            analisis    TEXT,
            run_time    TEXT,
            model_used  TEXT,
            source      TEXT    DEFAULT 'CNBC'
        )
    """)
    conn.commit()
    conn.close()

    # Migrasi: tambah kolom source kalau DB lama belum punya
    try:
        conn2 = sqlite3.connect(DB_PATH)
        conn2.execute("ALTER TABLE articles ADD COLUMN source TEXT DEFAULT 'CNBC'")
        conn2.commit()
        conn2.close()
    except Exception:
        pass  # Kolom sudah ada, abaikan

    log.info("Database siap: %s", DB_PATH)


def url_sudah_ada(url: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM articles WHERE url = ?", (url,))
    found = c.fetchone() is not None
    conn.close()
    return found


def simpan_artikel(data: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO articles
            (url, judul, tanggal, penulis, konten, ticker,
             skor, breakdown, verdict, highlight, analisis,
             run_time, model_used, source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("url"), data.get("judul"), data.get("tanggal"),
        data.get("penulis"), data.get("konten"), data.get("ticker"),
        data.get("skor", 0), json.dumps(data.get("breakdown", {}), ensure_ascii=False),
        data.get("verdict"), data.get("highlight"), data.get("analisis"),
        data.get("run_time"), data.get("model_used"),
        data.get("source", "CNBC"),
    ))
    conn.commit()
    conn.close()


def update_scoring(url: str, scoring: dict, model_used: str):
    """Update kolom scoring setelah analisis Claude."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE articles
        SET skor=?, breakdown=?, verdict=?, highlight=?, analisis=?, model_used=?
        WHERE url=?
    """, (
        scoring.get("skor_total", 0),
        json.dumps(scoring.get("breakdown", {}), ensure_ascii=False),
        scoring.get("verdict", ""),
        scoring.get("highlight", ""),
        scoring.get("analisis", ""),
        model_used,
        url,
    ))
    conn.commit()
    conn.close()


# ── Fetch halaman indeks ──────────────────────────────────────────────────────
def fetch_indeks(base_url: str, page: int, delay_min: float, delay_max: float) -> list[dict]:
    """
    Ambil daftar artikel dari halaman indeks CNBC.
    Return: list of { url, judul, tanggal_raw }
    """
    url = f"{base_url}?page={page}"
    log.info("[CNBC] Scraping indeks page %d → %s", page, url)

    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[CNBC] Gagal fetch indeks page %d: %s", page, e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []

    items = soup.select("article.list-item, div.list-item, div.detail__list-item")

    if not items:
        log.warning("[CNBC] Selector utama tidak ditemukan, pakai fallback link scraping")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/market/" in href and any(
                part in href for part in ["-17-", "-18-", "-19-", "-20-", "-21-"]
            ):
                full_url = href if href.startswith("http") else urljoin("https://www.cnbcindonesia.com", href)
                if full_url not in seen:
                    seen.add(full_url)
                    judul_text = a.get_text(strip=True)
                    if len(judul_text) > 20:
                        articles.append({"url": full_url, "judul": judul_text, "tanggal_raw": ""})
        log.info("[CNBC] Fallback menemukan %d artikel di page %d", len(articles), page)
        return articles

    for item in items:
        a_tag = item.find("a", href=True)
        if not a_tag:
            continue
        href = a_tag["href"]
        full_url = href if href.startswith("http") else urljoin("https://www.cnbcindonesia.com", href)

        judul_el = item.select_one("h2, h3, .list-item__title, .title")
        judul    = judul_el.get_text(strip=True) if judul_el else a_tag.get_text(strip=True)

        tgl_el   = item.select_one("time, .list-item__date, .date")
        tgl_raw  = tgl_el.get_text(strip=True) if tgl_el else ""

        if full_url and judul:
            articles.append({"url": full_url, "judul": judul, "tanggal_raw": tgl_raw})

    log.info("[CNBC] Ditemukan %d artikel di page %d", len(articles), page)
    return articles


# ── Fetch isi artikel ─────────────────────────────────────────────────────────
def fetch_artikel(url: str, delay_min: float, delay_max: float) -> dict | None:
    """
    Buka halaman artikel dan ekstrak konten lengkap.
    Return: { url, judul, tanggal, penulis, konten, source }
    """
    log.info("[CNBC] Membaca artikel: %s", url)
    try:
        time.sleep(random.uniform(delay_min, delay_max))
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        log.error("[CNBC] Gagal fetch artikel %s: %s", url, e)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Judul ──
    judul = ""
    for sel in ["h1.detail__title", "h1.title", "h1", "meta[property='og:title']"]:
        el = soup.select_one(sel)
        if el:
            judul = el.get("content", "") or el.get_text(strip=True)
            break

    # ── Tanggal ──
    tanggal = ""
    for sel in ["div.detail__date", "time", "span.date", "meta[property='article:published_time']"]:
        el = soup.select_one(sel)
        if el:
            tanggal = el.get("content", "") or el.get("datetime", "") or el.get_text(strip=True)
            break

    # ── Penulis ──
    penulis = ""
    for sel in ["div.detail__author", "span.author", "a[rel='author']", "meta[name='author']"]:
        el = soup.select_one(sel)
        if el:
            penulis = el.get("content", "") or el.get_text(strip=True)
            break

    # ── Konten ──
    konten_parts = []
    for sel in ["div.detail__body-text", "div.detail-text", "article", "div.content-text"]:
        container = soup.select_one(sel)
        if container:
            for tag in container.select("script, style, ins, .ads, .advertisement, figure"):
                tag.decompose()
            paragraphs = container.find_all("p")
            if paragraphs:
                konten_parts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
                break

    if not konten_parts:
        all_p = soup.find_all("p")
        konten_parts = [p.get_text(strip=True) for p in all_p if len(p.get_text(strip=True)) > 50]

    konten = "\n\n".join(konten_parts)

    if len(konten) < 100:
        log.warning("[CNBC] Konten terlalu pendek (%d chars), skip: %s", len(konten), url)
        return None

    return {
        "url":     url,
        "judul":   judul or "Tanpa Judul",
        "tanggal": tanggal,
        "penulis": penulis,
        "konten":  konten,
        "source":  "CNBC",
    }


# ── Main scraping run ─────────────────────────────────────────────────────────
def run_scraper(config: dict) -> list[dict]:
    """
    Jalankan scraping CNBC, return list artikel baru yang siap dianalisis.
    """
    init_db()

    cnbc_cfg  = config.get("sources", {}).get("cnbc", {})
    if not cnbc_cfg.get("enabled", True):
        log.info("[CNBC] Source CNBC dinonaktifkan di config, skip.")
        return []

    base_url     = cnbc_cfg.get("source_url", "https://www.cnbcindonesia.com/market/indeks/5")
    pages        = cnbc_cfg.get("pages_per_run", 20)
    max_articles = cnbc_cfg.get("max_articles", 30)
    delay_min    = config["scraper"]["request_delay_min"]
    delay_max    = config["scraper"]["request_delay_max"]

    queue     = []
    seen_urls = set()

    for page in range(1, pages + 1):
        if len(queue) >= max_articles:
            break
        items = fetch_indeks(base_url, page, delay_min, delay_max)
        for item in items:
            if len(queue) >= max_articles:
                break
            url = item["url"]
            if url not in seen_urls and not url_sudah_ada(url):
                seen_urls.add(url)
                queue.append(item)

    log.info("[CNBC] Total artikel baru ditemukan: %d (max: %d)", len(queue), max_articles)

    hasil = []
    for item in queue:
        artikel = fetch_artikel(item["url"], delay_min, delay_max)
        if artikel:
            hasil.append(artikel)

    log.info("[CNBC] Berhasil dibaca: %d artikel", len(hasil))
    return hasil


if __name__ == "__main__":
    import sys
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    articles = run_scraper(cfg)
    print(f"\nTotal artikel baru: {len(articles)}")
    for a in articles[:3]:
        print(f"  - {a['judul'][:80]}")
