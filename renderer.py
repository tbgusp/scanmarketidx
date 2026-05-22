"""
renderer.py
Render hasil analisis menjadi HTML editorial-style (terinspirasi Substack/Medium).
Support multi-source: CNBC, Bloomberg, IDX Channel.
"""

import json
import os
import logging
from datetime import datetime

log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def kategori_dari_skor(skor, threshold):
    """Return (kategori_label, css_class, dot_color)"""
    if skor >= threshold["signal_kuat"]:
        return "SIGNAL KUAT", "signal-kuat", "#dc2626"
    elif skor >= threshold["radar"]:
        return "RADAR", "radar", "#ea580c"
    elif skor >= threshold["pantau"]:
        return "PANTAU", "pantau", "#ca8a04"
    else:
        return "NOISE", "noise", "#9ca3af"


def render_source_badge(source: str) -> str:
    """Render badge warna sumber artikel."""
    style_map = {
        "CNBC":          "background:#fff7ed;color:#ea580c;border:1px solid #ea580c44;",
        "Bloomberg":     "background:#eff6ff;color:#2563eb;border:1px solid #2563eb44;",
        "IDX":           "background:#f0fdf4;color:#16a34a;border:1px solid #16a34a44;",
        "IDNFinancials": "background:#fdf4ff;color:#9333ea;border:1px solid #9333ea44;",
        "EmitenNews":    "background:#fff1f2;color:#e11d48;border:1px solid #e11d4844;",
    }
    style = style_map.get(source, "background:#f3f4f6;color:#6b7280;border:1px solid #6b728044;")
    return f'<span class="source-badge" style="{style}">{source}</span>'


def render_breakdown_bar(breakdown, kategori_class):
    """Render bar chart mini untuk breakdown skor."""
    labels = {
        "aksi_korporasi":   ("Aksi Korporasi", 25),
        "nama_besar":       ("Nama Besar", 20),
        "low_base":         ("Low Base", 15),
        "sektor_panas":     ("Sektor Panas", 15),
        "validasi_resmi":   ("Validasi Resmi", 10),
        "momentum_ekstrem": ("Momentum", 10),
        "fundamental":      ("Fundamental", 5),
    }
    html = '<div class="breakdown-grid">'
    for key, (label, maks) in labels.items():
        val = breakdown.get(key, 0)
        pct = int((val / maks) * 100) if maks > 0 else 0
        html += f"""
        <div class="bd-row">
          <span class="bd-label">{label}</span>
          <div class="bd-bar-wrap">
            <div class="bd-bar bd-bar-{kategori_class}" style="width:{pct}%"></div>
          </div>
          <span class="bd-val">{val}/{maks}</span>
        </div>"""
    html += "</div>"
    return html


def render_key_highlights(analisis_data, has_deep):
    """
    Render Key Highlights — info SINGKAT yang bisa di-scan cepat.
    Hanya ditampilkan kalau ada data Sonnet (has_deep=True).
    """
    if not has_deep or not analisis_data:
        return ""

    items = []

    fields = [
        ("jenis_perubahan",      "Jenis Perubahan",   "tag-blue"),
        ("jenis_aset_diinjeksi", "Aset Diinjeksi",    "tag-purple"),
        ("nama_besar_disebut",   "Nama Besar",        "tag-green"),
        ("fase_saat_ini",        "Fase Saat Ini",     "tag-orange"),
    ]
    for key, label, tag_class in fields:
        val = analisis_data.get(key, "")
        if val:
            items.append(f'''
              <div class="kh-item">
                <span class="kh-label {tag_class}">{label}</span>
                <span class="kh-value">{val}</span>
              </div>''')

    risks = analisis_data.get("risk_flag", [])
    if risks:
        risk_items = "".join(f'<li>{r}</li>' for r in risks[:3])
        items.append(f'''
          <div class="kh-item">
            <span class="kh-label tag-red">Risk Flag</span>
            <ul class="kh-list">{risk_items}</ul>
          </div>''')

    milestones = analisis_data.get("milestone_penting", [])
    if milestones:
        ms_items = "".join(f'<li>{m}</li>' for m in milestones[:3])
        items.append(f'''
          <div class="kh-item">
            <span class="kh-label tag-gray">Milestone</span>
            <ul class="kh-list">{ms_items}</ul>
          </div>''')

    if not items:
        return ""

    return '<div class="key-highlights">' + "".join(items) + "</div>"


def render_deep_analysis(analisis_data):
    """Render analisis mendalam lengkap (panel terpisah)."""
    if not analisis_data or not isinstance(analisis_data, dict):
        return ""

    html = '<div class="deep-analysis">'

    konteks = analisis_data.get("konteks_bandarmologi", "")
    if konteks:
        html += f'''
        <div class="da-section">
          <div class="da-label">KONTEKS BANDARMOLOGI</div>
          <p class="da-text">{konteks}</p>
        </div>'''

    kesimpulan = analisis_data.get("kesimpulan", "")
    if kesimpulan:
        html += f'''
        <div class="da-section da-kesimpulan">
          <div class="da-label">KESIMPULAN</div>
          <p class="da-text da-text-emphasis">{kesimpulan}</p>
        </div>'''

    html += "</div>"
    return html


def render_artikel_card(artikel, threshold, idx):
    """Render satu kartu artikel editorial-style."""
    skor      = artikel.get("skor", 0)
    breakdown = artikel.get("breakdown", {})
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except Exception:
            breakdown = {}

    kategori, css_class, dot_color = kategori_dari_skor(skor, threshold)

    judul     = artikel.get("judul", "Tanpa Judul")
    url       = artikel.get("url", "#")
    tanggal   = artikel.get("tanggal", "")
    penulis   = artikel.get("penulis", "")
    highlight = artikel.get("highlight", "")
    ticker    = artikel.get("ticker", "")
    model     = artikel.get("model_used", "")
    analisis  = artikel.get("analisis", "")
    source    = artikel.get("source", "CNBC")

    # Bersihkan tanggal ISO
    if tanggal and "T" in tanggal:
        try:
            dt = datetime.fromisoformat(tanggal.replace("Z", "").split("+")[0].split(".")[0])
            tanggal = dt.strftime("%d %b %Y, %H:%M")
        except Exception:
            pass

    # Estimasi reading time
    konten_len = len(artikel.get("konten", ""))
    read_time  = max(1, konten_len // 1000)

    # Source badge
    source_badge_html = render_source_badge(source)

    # Badge ticker
    ticker_html = ""
    if ticker:
        tickers = [t.strip() for t in ticker.split(",") if t.strip()]
        ticker_html = " ".join(f'<span class="ticker-pill">{t}</span>' for t in tickers)

    # Model indicator
    model_short = "Haiku" if "haiku" in model.lower() else "Sonnet" if "sonnet" in model.lower() else model
    model_class = "model-haiku" if "Haiku" in model_short else "model-sonnet"

    # Parse analisis kalau ada (dari Sonnet)
    analisis_data = {}
    if analisis:
        try:
            analisis_data = json.loads(analisis) if isinstance(analisis, str) else analisis
        except Exception:
            analisis_data = {}

    has_deep = bool(analisis_data) and "sonnet" in model.lower()

    breakdown_html      = render_breakdown_bar(breakdown, css_class)
    key_highlights_html = render_key_highlights(analisis_data, has_deep)
    deep_analysis_html  = render_deep_analysis(analisis_data) if has_deep else ""

    skor_visual = f'<span class="skor-big skor-{css_class}">{skor}</span><span class="skor-max">/100</span>'

    expand_id = f"exp-{idx}"
    deep_id   = f"deep-{idx}"

    toggle_label = "Lihat Key Highlights & Breakdown Skor" if has_deep else "Lihat Breakdown Skor"

    return f"""
<article class="post-card">

  <div class="post-top">
    <span class="cat-dot" style="background:{dot_color}"></span>
    <span class="cat-label {css_class}">{kategori}</span>
    {source_badge_html}
    {ticker_html}
    <span class="post-score-inline">SKOR <strong class="skor-{css_class}">{skor}</strong></span>
  </div>

  <h2 class="post-title">
    <a href="{url}" target="_blank" rel="noopener">{judul}</a>
  </h2>

  {f'<p class="post-subtitle">{highlight}</p>' if highlight else ''}

  <div class="post-meta">
    {f'<span class="meta-author">{penulis}</span>' if penulis else ''}
    {f'<span class="meta-sep">·</span>' if penulis and tanggal else ''}
    {f'<span class="meta-date">{tanggal}</span>' if tanggal else ''}
    {f'<span class="meta-sep">·</span>' if (penulis or tanggal) else ''}
    <span class="meta-read">{read_time} MIN READ</span>
    <span class="meta-sep">·</span>
    <span class="meta-model {model_class}">{model_short}</span>
  </div>

  <div class="post-actions">
    <button class="btn-toggle" onclick="toggleDetail('{expand_id}', this)">
      <span class="ico">▾</span> {toggle_label}
    </button>
    {('<button class="btn-toggle btn-toggle-sonnet" onclick="toggleDetail(\'' + deep_id + '\', this)"><span class="ico">▾</span> Analisis Mendalam</button>') if deep_analysis_html else ''}
    <a href="{url}" target="_blank" rel="noopener" class="btn-read">Baca artikel →</a>
  </div>

  <div class="post-detail" id="{expand_id}" style="display:none">
    <div class="detail-inner">
      <div class="skor-display">
        {skor_visual}
        <span class="skor-verdict skor-verdict-{css_class}">{kategori}</span>
      </div>
      <div class="detail-grid">
        <div class="detail-col detail-col-breakdown">
          <div class="detail-col-title">Breakdown Skor</div>
          {breakdown_html}
        </div>
        {f'<div class="detail-col detail-col-highlights"><div class="detail-col-title">Key Highlights</div>{key_highlights_html}</div>' if key_highlights_html else ''}
      </div>
    </div>
  </div>

  {f'<div class="post-detail" id="{deep_id}" style="display:none"><div class="detail-inner">{deep_analysis_html}</div></div>' if deep_analysis_html else ''}

</article>"""


def render_section(label, css_class, articles, threshold, idx_offset):
    if not articles:
        return "", idx_offset
    count = len(articles)
    cards = []
    idx = idx_offset
    for a in articles:
        cards.append(render_artikel_card(a, threshold, idx))
        idx += 1
    cards_html = "\n".join(cards)
    return f"""
<section class="section section-{css_class}">
  <div class="section-divider">
    <span class="section-label {css_class}">{label}</span>
    <span class="section-line"></span>
    <span class="section-count">{count} artikel</span>
  </div>
  <div class="posts-list">
    {cards_html}
  </div>
</section>""", idx


def render_html(articles, config, run_time):
    threshold = config["score_threshold"]

    signal_kuat = sorted([a for a in articles if a.get("skor", 0) >= threshold["signal_kuat"]], key=lambda x: -x.get("skor", 0))
    radar       = sorted([a for a in articles if threshold["radar"] <= a.get("skor", 0) < threshold["signal_kuat"]], key=lambda x: -x.get("skor", 0))
    pantau      = sorted([a for a in articles if threshold["pantau"] <= a.get("skor", 0) < threshold["radar"]], key=lambda x: -x.get("skor", 0))
    noise       = sorted([a for a in articles if a.get("skor", 0) < threshold["pantau"]], key=lambda x: -x.get("skor", 0))

    total  = len(articles)
    run_dt = datetime.fromisoformat(run_time) if run_time else datetime.now()
    run_str = run_dt.strftime("%d %B %Y")
    run_jam = run_dt.strftime("%H:%M WIB")
    sesi    = "Pagi" if run_dt.hour < 12 else "Sore"

    bulan_id = {
        "January":"Januari","February":"Februari","March":"Maret","April":"April",
        "May":"Mei","June":"Juni","July":"Juli","August":"Agustus",
        "September":"September","October":"Oktober","November":"November","December":"Desember"
    }
    for en, id_ in bulan_id.items():
        run_str = run_str.replace(en, id_)

    # Hitung per sumber
    n_cnbc      = len([a for a in articles if a.get("source", "CNBC") == "CNBC"])
    n_bloomberg = len([a for a in articles if a.get("source") == "Bloomberg"])
    n_idx       = len([a for a in articles if a.get("source") == "IDX"])
    n_idn       = len([a for a in articles if a.get("source") == "IDNFinancials"])
    n_emiten    = len([a for a in articles if a.get("source") == "EmitenNews"])

    idx = 0
    section_signal, idx = render_section("SIGNAL KUAT", "signal-kuat", signal_kuat, threshold, idx)
    section_radar,  idx = render_section("RADAR",       "radar",       radar,       threshold, idx)
    section_pantau, idx = render_section("PANTAU",      "pantau",      pantau,      threshold, idx)
    section_noise,  idx = render_section("NOISE",       "noise",       noise,       threshold, idx)

    source_stat_html = ""
    if n_cnbc > 0 or n_bloomberg > 0 or n_idx > 0:
        source_stat_html = f"""
    <div class="source-stats">
      <span class="src-pill" style="background:#fff7ed;color:#ea580c;border:1px solid #ea580c33;">CNBC {n_cnbc}</span>
      <span class="src-pill" style="background:#eff6ff;color:#2563eb;border:1px solid #2563eb33;">Bloomberg {n_bloomberg}</span>
      <span class="src-pill" style="background:#f0fdf4;color:#16a34a;border:1px solid #16a34a33;">IDX {n_idx}</span>
      <span class="src-pill" style="background:#fdf4ff;color:#9333ea;border:1px solid #9333ea33;">IDNFinancials {n_idn}</span>
      <span class="src-pill" style="background:#fff1f2;color:#e11d48;border:1px solid #e11d4833;">EmitenNews {n_emiten}</span>
    </div>"""

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Scan — {run_str} ({sesi})</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:          #ffffff;
    --bg-soft:     #fafafa;
    --bg-detail:   #f7f7f5;
    --border:      #e8e8e3;
    --border-soft: #f0f0eb;
    --text:        #1a1a1a;
    --text-soft:   #4a4a4a;
    --text-muted:  #8a8a85;
    --text-dim:    #b0b0a8;
    --accent:      #7c5cfc;

    --signal-kuat: #dc2626;
    --radar:       #ea580c;
    --pantau:      #ca8a04;
    --noise:       #6b7280;

    --signal-kuat-bg: rgba(220,38,38,.08);
    --radar-bg:       rgba(234,88,12,.08);
    --pantau-bg:      rgba(202,138,4,.10);
    --noise-bg:       rgba(107,114,128,.08);

    --serif: 'Spectral', 'Charter', 'Georgia', serif;
    --sans:  'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  }}

  html {{ scroll-behavior: smooth; -webkit-font-smoothing: antialiased; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    font-size: 16px;
    line-height: 1.6;
    min-height: 100vh;
  }}

  .site-header {{
    border-bottom: 1px solid var(--border);
    padding: 22px 32px;
    position: sticky;
    top: 0;
    z-index: 100;
    backdrop-filter: blur(8px);
    background: rgba(255,255,255,.92);
  }}
  .header-inner {{
    max-width: 720px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .brand {{
    font-family: var(--serif);
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: var(--text);
  }}
  .brand-accent {{ color: var(--signal-kuat); }}
  .header-meta {{
    font-size: 12px;
    color: var(--text-muted);
    display: flex;
    gap: 14px;
    align-items: center;
  }}
  .header-meta strong {{ color: var(--text); font-weight: 600; }}
  .sesi-pill {{
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 100px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--text-soft);
  }}

  .lead {{
    max-width: 720px;
    margin: 0 auto;
    padding: 32px 32px 24px;
    border-bottom: 1px solid var(--border-soft);
  }}
  .lead-date {{
    font-size: 13px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 600;
    margin-bottom: 12px;
  }}
  .lead-title {{
    font-family: var(--serif);
    font-size: 36px;
    font-weight: 700;
    line-height: 1.2;
    letter-spacing: -0.8px;
    color: var(--text);
    margin-bottom: 14px;
  }}
  .lead-sub {{
    font-size: 17px;
    color: var(--text-soft);
    line-height: 1.55;
    font-family: var(--serif);
  }}
  .stats-row {{
    display: flex;
    gap: 28px;
    margin-top: 20px;
    flex-wrap: wrap;
    align-items: flex-end;
  }}
  .stat {{
    display: flex;
    flex-direction: column;
    gap: 2px;
  }}
  .stat-num {{
    font-family: var(--serif);
    font-size: 24px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }}
  .stat-label {{
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
  }}
  .stat-num.signal-kuat {{ color: var(--signal-kuat); }}
  .stat-num.radar       {{ color: var(--radar); }}
  .stat-num.pantau      {{ color: var(--pantau); }}

  .source-stats {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 16px;
  }}
  .src-pill {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding: 3px 9px;
    border-radius: 100px;
  }}

  .main {{
    max-width: 720px;
    margin: 0 auto;
    padding: 8px 32px 80px;
  }}

  .section {{ margin-top: 24px; }}
  .section-divider {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 32px 0 8px;
  }}
  .section-label {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 4px 10px;
    border-radius: 4px;
  }}
  .section-label.signal-kuat {{ background: var(--signal-kuat-bg); color: var(--signal-kuat); }}
  .section-label.radar       {{ background: var(--radar-bg); color: var(--radar); }}
  .section-label.pantau      {{ background: var(--pantau-bg); color: var(--pantau); }}
  .section-label.noise       {{ background: var(--noise-bg); color: var(--noise); }}
  .section-line {{
    flex: 1;
    height: 1px;
    background: var(--border);
  }}
  .section-count {{
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 500;
  }}

  .posts-list {{ display: flex; flex-direction: column; }}
  .post-card {{
    padding: 26px 0;
    border-bottom: 1px solid var(--border-soft);
  }}
  .post-card:last-child {{ border-bottom: none; }}

  .post-top {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
  }}
  .cat-dot {{
    width: 18px;
    height: 18px;
    border-radius: 50%;
    flex-shrink: 0;
    position: relative;
  }}
  .cat-dot::after {{
    content: '';
    position: absolute;
    top: 4px; left: 8px;
    width: 2px; height: 10px;
    background: rgba(255,255,255,.85);
    transform: rotate(20deg);
    border-radius: 2px;
  }}
  .cat-label {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
  }}
  .cat-label.signal-kuat {{ color: var(--signal-kuat); }}
  .cat-label.radar       {{ color: var(--radar); }}
  .cat-label.pantau      {{ color: var(--pantau); }}
  .cat-label.noise       {{ color: var(--noise); }}

  .source-badge {{
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 2px 8px;
    border-radius: 100px;
  }}

  .ticker-pill {{
    font-family: var(--sans);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 2px 7px;
    border-radius: 100px;
  }}

  .post-score-inline {{
    margin-left: auto;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--text-muted);
  }}
  .post-score-inline strong {{
    font-family: var(--serif);
    font-size: 17px;
    margin-left: 4px;
  }}
  .skor-signal-kuat {{ color: var(--signal-kuat); }}
  .skor-radar       {{ color: var(--radar); }}
  .skor-pantau      {{ color: var(--pantau); }}
  .skor-noise       {{ color: var(--noise); }}

  .post-title {{
    font-family: var(--serif);
    font-size: 22px;
    font-weight: 700;
    line-height: 1.25;
    letter-spacing: -0.4px;
    margin-bottom: 10px;
  }}
  .post-title a {{
    color: var(--text);
    text-decoration: none;
    transition: color .15s;
  }}
  .post-title a:hover {{ color: var(--accent); }}

  .post-subtitle {{
    font-family: var(--serif);
    font-size: 16px;
    color: var(--text-soft);
    line-height: 1.5;
    margin-bottom: 14px;
  }}

  .post-meta {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    text-transform: uppercase;
    margin-bottom: 12px;
  }}
  .meta-sep {{ color: var(--text-dim); }}
  .meta-model.model-sonnet {{ color: #059669; }}
  .meta-model.model-haiku  {{ color: #2563eb; }}

  .post-actions {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .btn-toggle {{
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-soft);
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: all .15s;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }}
  .btn-toggle:hover {{
    background: var(--bg-soft);
    border-color: #d8d8d3;
    color: var(--text);
  }}
  .btn-toggle .ico {{
    font-size: 10px;
    transition: transform .2s;
  }}
  .btn-toggle.open .ico {{ transform: rotate(180deg); }}
  .btn-toggle-sonnet {{
    border-color: rgba(5,150,105,.3);
    color: #059669;
  }}
  .btn-toggle-sonnet:hover {{
    background: rgba(5,150,105,.05);
    border-color: rgba(5,150,105,.5);
  }}
  .btn-read {{
    margin-left: auto;
    color: var(--accent);
    text-decoration: none;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
  }}
  .btn-read:hover {{ text-decoration: underline; }}

  .post-detail {{
    margin-top: 14px;
    background: var(--bg-detail);
    border: 1px solid var(--border-soft);
    border-radius: 8px;
    overflow: hidden;
    animation: slideDown .25s ease;
  }}
  @keyframes slideDown {{
    from {{ opacity: 0; transform: translateY(-4px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .detail-inner {{ padding: 18px 20px; }}

  .skor-display {{
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 18px;
    padding-bottom: 14px;
    border-bottom: 1px solid var(--border-soft);
  }}
  .skor-big {{
    font-family: var(--serif);
    font-size: 56px;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -2px;
  }}
  .skor-max {{
    font-family: var(--serif);
    font-size: 20px;
    color: var(--text-muted);
    font-weight: 500;
  }}
  .skor-verdict {{
    margin-left: auto;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 5px 11px;
    border-radius: 4px;
    align-self: center;
  }}
  .skor-verdict-signal-kuat {{ background: var(--signal-kuat-bg); color: var(--signal-kuat); }}
  .skor-verdict-radar       {{ background: var(--radar-bg); color: var(--radar); }}
  .skor-verdict-pantau      {{ background: var(--pantau-bg); color: var(--pantau); }}
  .skor-verdict-noise       {{ background: var(--noise-bg); color: var(--noise); }}

  .breakdown-grid {{
    display: flex;
    flex-direction: column;
    gap: 9px;
  }}
  .bd-row {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .bd-label {{
    font-size: 12px;
    font-weight: 500;
    color: var(--text-soft);
    width: 130px;
    flex-shrink: 0;
  }}
  .bd-bar-wrap {{
    flex: 1;
    height: 6px;
    background: #ececea;
    border-radius: 100px;
    overflow: hidden;
  }}
  .bd-bar {{
    height: 100%;
    border-radius: 100px;
    transition: width .4s ease;
  }}
  .bd-bar-signal-kuat {{ background: var(--signal-kuat); }}
  .bd-bar-radar       {{ background: var(--radar); }}
  .bd-bar-pantau      {{ background: var(--pantau); }}
  .bd-bar-noise       {{ background: var(--noise); }}
  .bd-val {{
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    width: 40px;
    text-align: right;
  }}

  .detail-grid {{
    display: grid;
    grid-template-columns: 1fr 1.3fr;
    gap: 28px;
  }}
  .detail-col-title {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-soft);
  }}

  .key-highlights {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .kh-item {{
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .kh-label {{
    display: inline-block;
    width: fit-content;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 4px;
    margin-bottom: 2px;
  }}
  .tag-blue   {{ background: rgba(37,99,235,.10);   color: #2563eb; }}
  .tag-purple {{ background: rgba(124,92,252,.10);  color: #7c5cfc; }}
  .tag-green  {{ background: rgba(5,150,105,.10);   color: #059669; }}
  .tag-orange {{ background: rgba(234,88,12,.10);   color: #ea580c; }}
  .tag-red    {{ background: rgba(220,38,38,.10);   color: #dc2626; }}
  .tag-gray   {{ background: rgba(107,114,128,.10); color: #6b7280; }}

  .kh-value {{
    font-family: var(--serif);
    font-size: 14px;
    color: var(--text);
    line-height: 1.5;
  }}
  .kh-list {{
    font-family: var(--serif);
    font-size: 13.5px;
    color: var(--text);
    line-height: 1.55;
    padding-left: 16px;
    margin-top: 2px;
  }}
  .kh-list li {{ margin-bottom: 3px; }}

  .deep-analysis {{
    display: flex;
    flex-direction: column;
    gap: 18px;
  }}
  .da-section {{
    display: flex;
    flex-direction: column;
    gap: 8px;
  }}
  .da-section.da-kesimpulan {{
    padding-top: 14px;
    border-top: 1px solid var(--border-soft);
  }}
  .da-label {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: var(--text-muted);
  }}
  .da-text {{
    font-family: var(--serif);
    font-size: 15px;
    color: var(--text);
    line-height: 1.65;
  }}
  .da-text-emphasis {{
    font-weight: 500;
    color: var(--text);
    border-left: 3px solid var(--accent);
    padding-left: 14px;
  }}

  .empty-state {{
    text-align: center;
    padding: 80px 24px;
    color: var(--text-muted);
    font-family: var(--serif);
    font-size: 16px;
    font-style: italic;
  }}

  .page-footer {{
    text-align: center;
    padding: 32px 24px;
    font-size: 12px;
    color: var(--text-muted);
    border-top: 1px solid var(--border);
    margin-top: 48px;
  }}
  .page-footer strong {{ color: var(--text-soft); }}

  @media (max-width: 640px) {{
    .lead-title {{ font-size: 28px; }}
    .lead-sub {{ font-size: 16px; }}
    .post-title {{ font-size: 20px; }}
    .post-subtitle {{ font-size: 15px; }}
    .header-meta {{ font-size: 11px; gap: 8px; }}
    .lead, .main, .site-header {{ padding-left: 20px; padding-right: 20px; }}
    .stats-row {{ gap: 18px; }}
    .skor-big {{ font-size: 44px; }}
    .post-score-inline {{ margin-left: 0; width: 100%; margin-top: 4px; }}
    .btn-read {{ margin-left: 0; width: 100%; margin-top: 8px; text-align: center; }}
    .detail-grid {{ grid-template-columns: 1fr; gap: 24px; }}
  }}

  ::-webkit-scrollbar {{ width: 10px; }}
  ::-webkit-scrollbar-track {{ background: var(--bg-soft); }}
  ::-webkit-scrollbar-thumb {{ background: #d8d8d3; border-radius: 5px; }}
  ::-webkit-scrollbar-thumb:hover {{ background: #b8b8b3; }}
</style>
</head>
<body>

<header class="site-header">
  <div class="header-inner">
    <div class="brand">Market<span class="brand-accent">Scan</span></div>
    <div class="header-meta">
      <span><strong>{run_str}</strong></span>
      <span class="sesi-pill">SESI {sesi.upper()} · {run_jam}</span>
    </div>
  </div>
</header>

<div class="lead">
  <div class="lead-date">Edisi {sesi} — {run_str}</div>
  <h1 class="lead-title">Hari ini di pasar saham Indonesia.</h1>
  <p class="lead-sub">
    {len(signal_kuat)} sinyal kuat, {len(radar)} di radar, {len(pantau)} layak dipantau —
    dari {total} artikel yang dianalisis dari CNBC, Bloomberg, IDX Channel, IDN Financials, dan Emiten News.
  </p>

  <div class="stats-row">
    <div class="stat">
      <span class="stat-num signal-kuat">{len(signal_kuat)}</span>
      <span class="stat-label">Signal Kuat</span>
    </div>
    <div class="stat">
      <span class="stat-num radar">{len(radar)}</span>
      <span class="stat-label">Radar</span>
    </div>
    <div class="stat">
      <span class="stat-num pantau">{len(pantau)}</span>
      <span class="stat-label">Pantau</span>
    </div>
    <div class="stat">
      <span class="stat-num" style="color:var(--text-soft)">{total}</span>
      <span class="stat-label">Total Artikel</span>
    </div>
  </div>
  {source_stat_html}
</div>

<main class="main">
  {section_signal}
  {section_radar}
  {section_pantau}
  {section_noise}
  {'<div class="empty-state">Tidak ada artikel baru ditemukan pada run ini.</div>' if not articles else ''}
</main>

<footer class="page-footer">
  <strong>Market Scan</strong> · Sistem analisis berita otomatis ·
  Bukan rekomendasi investasi · {run_str} {run_jam}
</footer>

<script>
function toggleDetail(id, btn) {{
  var el = document.getElementById(id);
  if (!el) return;
  var isHidden = el.style.display === 'none' || !el.style.display;
  el.style.display = isHidden ? 'block' : 'none';
  if (btn) btn.classList.toggle('open', isHidden);
}}
</script>

</body>
</html>"""


def save_html(articles, config, run_time):
    html_content = render_html(articles, config, run_time)

    dt       = datetime.fromisoformat(run_time) if run_time else datetime.now()
    filename = f"market_scan_{dt.strftime('%Y-%m-%d_%H-%M')}.html"
    out_path = os.path.join(BASE_DIR, "output", filename)

    os.makedirs(os.path.join(BASE_DIR, "output"), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    log.info("HTML disimpan: %s", out_path)
    return out_path
