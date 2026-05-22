"""
analyzer.py
Scoring artikel menggunakan Claude API — hybrid Haiku (screening) + Sonnet (deep analysis)
"""

import json
import time
import logging
import os
import re
import random
import anthropic
from datetime import datetime

log = logging.getLogger(__name__)

# ── Prompt screening (Haiku) ─────────────────────────────────────────────────
PROMPT_SCREENING = """Kamu adalah analis saham IDX yang bertugas mendeteksi potensi multibagger dari berita.

Berikan skor untuk artikel berikut berdasarkan 7 parameter:

1. AKSI_KORPORASI — Ada aksi korporasi atau transformasi besar: backdoor listing, merger, akuisisi, rights issue/PMHMETD, kontrak jumbo, IPO sektor baru, perubahan bisnis fundamental. Maks 25.
2. NAMA_BESAR — Disebut nama besar: konglomerat, grup besar, tokoh dengan koneksi kuat, investor strategis, atau pengendali baru masuk. Maks 20.
3. LOW_BASE — Emiten kecil, harga rendah, market cap kecil, float/likuiditas sempit, papan pemantauan, atau kurang populer. Maks 15.
4. SEKTOR_PANAS — Masuk narasi sektor panas: digital, AI, data center, fiber, internet, kripto, hilirisasi, energi, properti premium, offshore, atau transformasi bisnis ke sektor lebih menarik. Maks 15.
5. VALIDASI_RESMI — Ada validasi resmi: keterbukaan informasi BEI, perubahan pengendali resmi, kontrak ditandatangani, merger diumumkan, akuisisi selesai. Maks 10.
6. MOMENTUM_EKSTREM — Ada momentum ekstrem: ARA/ARB, suspensi BEI, UMA, FCA, volume spike besar, harga naik ratusan persen. Maks 10.
7. FUNDAMENTAL — Fundamental mulai membaik: laba berbalik positif, pendapatan naik signifikan, margin membaik. Maks 5.

PENTING: Rumor atau kabar beredar tentang nama besar tetap diberi skor tinggi meski belum ada konfirmasi resmi.

Jawab HANYA dalam format JSON berikut, tidak ada teks lain, tidak ada markdown:
{
  "skor_total": 0,
  "breakdown": {
    "aksi_korporasi": 0,
    "nama_besar": 0,
    "low_base": 0,
    "sektor_panas": 0,
    "validasi_resmi": 0,
    "momentum_ekstrem": 0,
    "fundamental": 0
  },
  "ticker": [],
  "verdict": "",
  "highlight": ""
}

Untuk verdict gunakan salah satu: "SIGNAL KUAT", "RADAR", "PANTAU", "NOISE"
Untuk highlight: 1-2 kalimat singkat poin paling menarik dari artikel ini."""


# ── Prompt deep analysis (Sonnet) ────────────────────────────────────────────
PROMPT_DEEP = """Kamu adalah analis saham IDX senior dengan keahlian bandarmologi, Wyckoff, dan deteksi Smart Money.

Artikel ini sudah lolos screening awal dengan skor tinggi. Berikan analisis mendalam.

Jawab HANYA dalam format JSON berikut, tidak ada teks lain, tidak ada markdown:
{
  "skor_total": 0,
  "breakdown": {
    "aksi_korporasi": 0,
    "nama_besar": 0,
    "low_base": 0,
    "sektor_panas": 0,
    "validasi_resmi": 0,
    "momentum_ekstrem": 0,
    "fundamental": 0
  },
  "ticker": [],
  "verdict": "",
  "highlight": "",
  "analisis": {
    "jenis_perubahan": "",
    "jenis_aset_diinjeksi": "",
    "nama_besar_disebut": "",
    "fase_saat_ini": "",
    "milestone_penting": [],
    "risk_flag": [],
    "konteks_bandarmologi": "",
    "kesimpulan": ""
  }
}

Untuk jenis_perubahan: jelaskan tipe transformasi (backdoor listing / change of control / merger / akuisisi / rights issue / transformasi bisnis / dll)
Untuk jenis_aset_diinjeksi: aset atau bisnis baru yang masuk ke emiten
Untuk fase_saat_ini: fase Wyckoff atau fase narasi (pre-akuisisi / post-akuisisi / akumulasi / distribusi / dll)
Untuk milestone_penting: list tanggal atau event penting dari artikel
Untuk risk_flag: list risiko yang perlu diwaspadai
Untuk konteks_bandarmologi: apakah ada tanda Smart Money sudah masuk sebelum berita
Untuk kesimpulan: 2-3 kalimat verdict akhir apakah artikel ini layak ditindaklanjuti"""


def parse_json_response(text: str) -> dict:
    """Ekstrak JSON dari response Claude secara aman."""
    text = text.strip()
    # Hapus markdown code block kalau ada
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Coba cari JSON di dalam teks
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        log.error("Gagal parse JSON: %s", text[:200])
        return {}


def scoring_haiku(artikel: dict, client: anthropic.Anthropic, model: str) -> dict:
    """Screening awal dengan Haiku."""
    konten = f"Judul: {artikel['judul']}\nTanggal: {artikel['tanggal']}\n\n{artikel['konten']}"
    # Batasi konten maksimal 3000 karakter untuk efisiensi
    if len(konten) > 3000:
        konten = konten[:3000] + "..."

    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=600,
                system=PROMPT_SCREENING,
                messages=[{"role": "user", "content": konten}]
            )
            raw = resp.content[0].text
            result = parse_json_response(raw)
            if result and "skor_total" in result:
                return result
        except Exception as e:
            log.warning("Haiku attempt %d gagal untuk %s: %s", attempt + 1, artikel["url"], e)
            time.sleep(2 ** attempt)

    # Fallback kalau semua retry gagal
    return {
        "skor_total": 0,
        "breakdown": {k: 0 for k in ["aksi_korporasi","nama_besar","low_base","sektor_panas","validasi_resmi","momentum_ekstrem","fundamental"]},
        "ticker": [],
        "verdict": "NOISE",
        "highlight": "Gagal dianalisis."
    }


def scoring_sonnet(artikel: dict, client: anthropic.Anthropic, model: str, skor_haiku: dict) -> dict:
    """Analisis mendalam dengan Sonnet untuk artikel skor tinggi."""
    konten = f"Judul: {artikel['judul']}\nTanggal: {artikel['tanggal']}\nPenulis: {artikel['penulis']}\n\n{artikel['konten']}"
    # Untuk Sonnet boleh konten lebih panjang
    if len(konten) > 6000:
        konten = konten[:6000] + "..."

    # Sertakan skor Haiku sebagai konteks awal
    prefix = f"Skor screening awal (Haiku): {skor_haiku.get('skor_total', 0)}/100\nHighlight awal: {skor_haiku.get('highlight', '')}\n\nArtikel:\n"
    konten = prefix + konten

    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=1500,
                system=PROMPT_DEEP,
                messages=[{"role": "user", "content": konten}]
            )
            raw = resp.content[0].text
            result = parse_json_response(raw)
            if result and "skor_total" in result:
                return result
        except Exception as e:
            log.warning("Sonnet attempt %d gagal untuk %s: %s", attempt + 1, artikel["url"], e)
            time.sleep(2 ** attempt)

    # Fallback ke hasil Haiku kalau Sonnet gagal
    log.error("Sonnet gagal semua retry, fallback ke hasil Haiku: %s", artikel["url"])
    return skor_haiku


def analyze_articles(articles: list[dict], config: dict) -> list[dict]:
    """
    Analisis semua artikel:
    - Semua artikel → Haiku (screening)
    - Artikel skor ≥ threshold → Sonnet (deep analysis)
    Return: list artikel dengan hasil scoring lengkap
    """
    api_key   = config["anthropic_api_key"]
    model_h   = config["model"]["screening"]
    model_s   = config["model"]["deep_analysis"]
    threshold = config["score_threshold"]["signal_kuat"]

    client = anthropic.Anthropic(api_key=api_key)
    results = []
    run_time = datetime.now().isoformat()

    total = len(articles)
    log.info("Mulai analisis %d artikel...", total)

    for i, artikel in enumerate(articles, 1):
        log.info("[%d/%d] Analisis: %s", i, total, artikel["judul"][:60])

        # Step 1: Screening dengan Haiku
        skor_haiku = scoring_haiku(artikel, client, model_h)
        skor_total = skor_haiku.get("skor_total", 0)
        model_used = model_h

        log.info("  Haiku skor: %d — %s", skor_total, skor_haiku.get("verdict", ""))

        final_scoring = skor_haiku

        # Step 2: Deep analysis dengan Sonnet kalau skor tinggi
        if skor_total >= threshold:
            log.info("  → Skor ≥ %d, upgrade ke Sonnet...", threshold)
            skor_sonnet = scoring_sonnet(artikel, client, model_s, skor_haiku)
            final_scoring = skor_sonnet
            model_used = model_s
            log.info("  Sonnet skor: %d — %s", skor_sonnet.get("skor_total", 0), skor_sonnet.get("verdict", ""))

        # Gabungkan data artikel + scoring
        hasil = {
            **artikel,
            "skor":       final_scoring.get("skor_total", 0),
            "breakdown":  final_scoring.get("breakdown", {}),
            "verdict":    final_scoring.get("verdict", "NOISE"),
            "highlight":  final_scoring.get("highlight", ""),
            "ticker":     ",".join(final_scoring.get("ticker", [])),
            "analisis":   json.dumps(final_scoring.get("analisis", {}), ensure_ascii=False),
            "run_time":   run_time,
            "model_used": model_used,
        }
        results.append(hasil)

        # Delay antar API call supaya tidak rate limit
        time.sleep(random.uniform(0.5, 1.5))

    log.info("Analisis selesai. %d artikel diproses.", len(results))
    return results


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(BASE_DIR, "config.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)

    # Test dengan satu artikel dummy
    test = [{
        "url": "https://test.com",
        "judul": "Agung Sedayu Caplok 80% Saham PANI, BEI Suspensi",
        "tanggal": "14 Oktober 2021",
        "penulis": "Test",
        "konten": "Bursa Efek Indonesia menghentikan sementara perdagangan saham PANI setelah Agung Sedayu Group mengakuisisi 80% saham melalui backdoor listing senilai Rp 54 miliar. Saham melesat 142% dalam sepekan."
    }]
    results = analyze_articles(test, cfg)
    print(json.dumps(results[0], indent=2, ensure_ascii=False))
