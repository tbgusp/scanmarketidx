"""
renderer.py
Render hasil analisis menjadi HTML editorial-style (terinspirasi Substack/Medium).
Support multi-source: CNBC, Bloomberg, IDX Channel, dll.
Python 3.11 compatible — tidak ada backslash di dalam f-string expressions.
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
        "InvestorID":    "background:#fefce8;color:#ca8a04;border:1px solid #ca8a0444;",
        "Kontan":        "background:#f0f9ff;color:#0284c7;border:1px solid #0284c744;",
        "Liputan6":      "background:#fdf2f8;color:#9d174d;border:1px solid #9d174d44;",
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
    rows = []
    for key, (label, max_val) in labels.items():
        val  = breakdown.get(key, 0)
        pct  = int((val / max_val) * 100) if max_val else 0
        rows.append(f"""
        <div class="bar-row">
          <span class="bar-label">{label}</span>
          <div class="bar-track">
            <div class="bar-fill bar-fill-{kategori_class}" style="width:{pct}%"></div>
          </div>
          <span class="bar-val">{val}/{max_val}</span>
        </div>""")
    return "\n".join(rows)


def render_deep_analysis(analisis_json: str) -> str:
    """Render deep analysis dari Sonnet ke HTML."""
    if not analisis_json or analisis_json == "{}":
        return ""
    try:
        a = json.loads(analisis_json)
    except Exception:
        return ""
    if not a:
        return ""

    rows = []
    field_map = [
        ("jenis_perubahan",    "Jenis Perubahan"),
        ("jenis_aset_diinjeksi", "Aset Diinjeksi"),
        ("nama_besar_disebut",  "Nama Besar"),
        ("fase_saat_ini",       "Fase Saat Ini"),
        ("konteks_bandarmologi","Konteks Bandar"),
        ("kesimpulan",          "Kesimpulan"),
    ]
    for key, label in field_map:
        val = a.get(key, "")
        if val:
            rows.append(f'<div class="deep-row"><span class="deep-label">{label}</span><span class="deep-val">{val}</span></div>')

    milestones = a.get("milestone_penting", [])
    if milestones:
        items = "".join(f"<li>{m}</li>" for m in milestones)
        rows.append(f'<div class="deep-row"><span class="deep-label">Milestones</span><ul class="deep-list">{items}</ul></div>')

    risks = a.get("risk_flag", [])
    if risks:
        items = "".join(f"<li>{r}</li>" for r in risks)
        rows.append(f'<div class="deep-row"><span class="deep-label">Risk Flag</span><ul class="deep-list risk-list">{items}</ul></div>')

    return "\n".join(rows)


def render_artikel_card(artikel: dict, idx: int, threshold: dict) -> str:
    """Render satu kartu artikel."""
    skor     = artikel.get("skor", 0)
    kategori, css_class, _ = kategori_dari_skor(skor, threshold)
    judul    = artikel.get("judul", "Tanpa Judul")
    url      = artikel.get("url", "#")
    source   = artikel.get("source", "CNBC")
    tanggal  = artikel.get("tanggal", "")
    highlight= artikel.get("highlight", "")
    ticker   = artikel.get("ticker", "")
    breakdown= artikel.get("breakdown", {})
    analisis = artikel.get("analisis", "{}")

    expand_id    = f"detail-{idx}"
    deep_id      = f"deep-{idx}"
    toggle_label = "Lihat Detail"

    source_badge      = render_source_badge(source)
    breakdown_html    = render_breakdown_bar(breakdown, css_class)
    deep_analysis_html= render_deep_analysis(analisis)

    skor_visual = f'<span class="skor-number skor-{css_class}">{skor}</span>'

    ticker_html = ""
    if ticker:
        tickers = [t.strip() for t in ticker.split(",") if t.strip()]
        ticker_html = "".join(f'<span class="ticker-badge">{t}</span>' for t in tickers)

    key_highlights_html = f'<p class="highlight-text">{highlight}</p>' if highlight else ""

    # Build deep analysis button safely (no backslash in f-string)
    if deep_analysis_html:
        deep_btn = (
            '<button class="btn-toggle btn-toggle-sonnet" onclick="toggleDetail(\''
            + deep_id
            + '\', this)"><span class="ico">▾</span> Analisis Mendalam</button>'
        )
    else:
        deep_btn = ""

    # Build deep analysis section safely
    if deep_analysis_html:
        deep_section = (
            '<div class="post-detail" id="'
            + deep_id
            + '" style="display:none"><div class="detail-inner">'
            + deep_analysis_html
            + "</div></div>"
        )
    else:
        deep_section = ""

    # Build key highlights section safely
    if key_highlights_html:
        highlights_section = (
            '<div class="detail-col detail-col-highlights">'
            '<div class="detail-col-title">Key Highlights</div>'
            + key_highlights_html
            + "</div>"
        )
    else:
        highlights_section = ""

    return f"""
<article class="post post-{css_class}">
  <div class="post-header">
    <div class="post-meta">
      {source_badge}
      <span class="post-date">{tanggal}</span>
      {ticker_html}
    </div>
    <span class="verdict-badge verdict-{css_class}">{kategori}</span>
  </div>

  <h2 class="post-title">
    <a href="{url}" target="_blank" rel="noopener">{judul}</a>
  </h2>

  <div class="post-actions">
    <button class="btn-toggle" onclick="toggleDetail('{expand_id}', this)">
      <span class="ico">▾</span> {toggle_label}
    </button>
    {deep_btn}
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
        {highlights_section}
      </div>
    </div>
  </div>

  {deep_section}

</article>"""


def render_section(label, css_class, articles, threshold, idx_offset):
    if not articles:
        return "", idx_offset
    count = len(articles)
    cards = []
    idx   = idx_offset
    for a in articles:
        cards.append(render_artikel_card(a, idx, threshold))
        idx += 1
    cards_html = "\n".join(cards)
    return f"""
<section class="section section-{css_class}">
  <div class="section-header">
    <span class="section-dot dot-{css_class}"></span>
    <h2 class="section-title">{label}</h2>
    <span class="section-count">{count} artikel</span>
  </div>
  {cards_html}
</section>""", idx


def render_stats_bar(results, threshold):
    """Render bar statistik di atas halaman."""
    signal_kuat = sum(1 for r in results if r.get("skor", 0) >= threshold["signal_kuat"])
    radar       = sum(1 for r in results if threshold["radar"] <= r.get("skor", 0) < threshold["signal_kuat"])
    pantau      = sum(1 for r in results if threshold["pantau"] <= r.get("skor", 0) < threshold["radar"])
    noise       = sum(1 for r in results if r.get("skor", 0) < threshold["pantau"])
    total       = len(results)

    sources = {}
    for r in results:
        s = r.get("source", "CNBC")
        sources[s] = sources.get(s, 0) + 1
    source_html = "".join(
        f'<span class="stat-source">{s}: <b>{n}</b></span>'
        for s, n in sorted(sources.items())
    )

    return f"""
<div class="stats-bar">
  <div class="stats-counts">
    <span class="stat signal-kuat">🔴 Signal Kuat: <b>{signal_kuat}</b></span>
    <span class="stat radar">🟡 Radar: <b>{radar}</b></span>
    <span class="stat pantau">🟢 Pantau: <b>{pantau}</b></span>
    <span class="stat noise">⚪ Noise: <b>{noise}</b></span>
    <span class="stat total">Total: <b>{total}</b></span>
  </div>
  <div class="stats-sources">{source_html}</div>
</div>"""


def build_html(results: list, config: dict, run_time: str) -> str:
    """Build full HTML dari hasil analisis."""
    threshold = config["score_threshold"]

    try:
        dt       = datetime.fromisoformat(run_time)
        tgl_str  = dt.strftime("%A, %d %B %Y")
        jam_str  = dt.strftime("%H:%M WIB")
    except Exception:
        tgl_str = run_time
        jam_str = ""

    signal_kuat = [r for r in results if r.get("skor", 0) >= threshold["signal_kuat"]]
    radar       = [r for r in results if threshold["radar"] <= r.get("skor", 0) < threshold["signal_kuat"]]
    pantau      = [r for r in results if threshold["pantau"] <= r.get("skor", 0) < threshold["radar"]]
    noise       = [r for r in results if r.get("skor", 0) < threshold["pantau"]]

    stats_html = render_stats_bar(results, threshold)

    idx = 0
    sec_signal, idx = render_section("🔴 Signal Kuat",  "signal-kuat", signal_kuat, threshold, idx)
    sec_radar,  idx = render_section("🟡 Radar",        "radar",       radar,       threshold, idx)
    sec_pantau, idx = render_section("🟢 Pantau",       "pantau",      pantau,      threshold, idx)
    sec_noise,  idx = render_section("⚪ Noise",         "noise",       noise,       threshold, idx)

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Market Scan IDX — {tgl_str}</title>
  <style>
    :root {{
      --red:    #dc2626; --orange: #ea580c; --yellow: #ca8a04;
      --gray:   #6b7280; --blue:   #2563eb; --green:  #16a34a;
      --bg:     #f8fafc; --card:   #ffffff; --border: #e2e8f0;
      --text:   #1e293b; --muted:  #64748b;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            background: var(--bg); color: var(--text); line-height: 1.6; }}
    a {{ color: inherit; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}

    /* Layout */
    .container {{ max-width: 860px; margin: 0 auto; padding: 24px 16px; }}

    /* Header */
    .site-header {{ background: #0f172a; color: white; padding: 20px 0; margin-bottom: 24px; }}
    .site-header .container {{ display: flex; justify-content: space-between; align-items: center; }}
    .site-title {{ font-size: 1.4rem; font-weight: 700; letter-spacing: -0.5px; }}
    .site-meta {{ font-size: 0.85rem; color: #94a3b8; text-align: right; }}

    /* Stats bar */
    .stats-bar {{ background: white; border: 1px solid var(--border); border-radius: 10px;
                  padding: 14px 18px; margin-bottom: 24px; }}
    .stats-counts {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; font-size: 0.9rem; }}
    .stats-sources {{ display: flex; flex-wrap: wrap; gap: 8px; font-size: 0.8rem; color: var(--muted); }}
    .stat-source {{ background: #f1f5f9; padding: 2px 8px; border-radius: 4px; }}

    /* Section */
    .section {{ margin-bottom: 40px; }}
    .section-header {{ display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
                        padding-bottom: 10px; border-bottom: 2px solid var(--border); }}
    .section-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}
    .dot-signal-kuat {{ background: var(--red); }}
    .dot-radar {{ background: var(--orange); }}
    .dot-pantau {{ background: var(--yellow); }}
    .dot-noise {{ background: var(--gray); }}
    .section-title {{ font-size: 1.15rem; font-weight: 700; }}
    .section-count {{ margin-left: auto; font-size: 0.8rem; color: var(--muted);
                      background: #f1f5f9; padding: 2px 8px; border-radius: 12px; }}

    /* Article card */
    .post {{ background: white; border: 1px solid var(--border); border-radius: 10px;
             padding: 18px 20px; margin-bottom: 14px; transition: box-shadow .2s; }}
    .post:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,.08); }}
    .post-signal-kuat {{ border-left: 4px solid var(--red); }}
    .post-radar {{ border-left: 4px solid var(--orange); }}
    .post-pantau {{ border-left: 4px solid var(--yellow); }}
    .post-noise {{ border-left: 4px solid var(--gray); opacity: .75; }}

    .post-header {{ display: flex; justify-content: space-between; align-items: flex-start;
                    gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }}
    .post-meta {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
                  font-size: 0.78rem; color: var(--muted); }}
    .source-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;
                     font-weight: 600; white-space: nowrap; }}
    .ticker-badge {{ background: #dbeafe; color: #1d4ed8; padding: 1px 7px;
                     border-radius: 4px; font-size: 0.75rem; font-weight: 700; }}
    .verdict-badge {{ padding: 3px 10px; border-radius: 6px; font-size: 0.75rem;
                      font-weight: 700; white-space: nowrap; }}
    .verdict-signal-kuat {{ background: #fef2f2; color: var(--red); }}
    .verdict-radar {{ background: #fff7ed; color: var(--orange); }}
    .verdict-pantau {{ background: #fefce8; color: var(--yellow); }}
    .verdict-noise {{ background: #f9fafb; color: var(--gray); }}

    .post-title {{ font-size: 1rem; font-weight: 600; margin-bottom: 10px; line-height: 1.4; }}
    .post-title a:hover {{ color: var(--blue); }}

    .post-actions {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .btn-toggle {{ background: #f1f5f9; border: 1px solid var(--border); padding: 4px 12px;
                   border-radius: 6px; font-size: 0.8rem; cursor: pointer; color: var(--text); }}
    .btn-toggle:hover {{ background: #e2e8f0; }}
    .btn-toggle-sonnet {{ background: #eff6ff; border-color: #bfdbfe; color: var(--blue); }}
    .btn-toggle-sonnet:hover {{ background: #dbeafe; }}
    .btn-read {{ font-size: 0.8rem; color: var(--blue); padding: 4px 12px;
                 border: 1px solid #bfdbfe; border-radius: 6px; background: #eff6ff; }}
    .btn-read:hover {{ background: #dbeafe; text-decoration: none; }}
    .ico {{ display: inline-block; transition: transform .2s; }}

    /* Detail panel */
    .post-detail {{ margin-top: 14px; border-top: 1px solid var(--border); padding-top: 14px; }}
    .detail-inner {{ }}
    .skor-display {{ display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }}
    .skor-number {{ font-size: 2.2rem; font-weight: 800; line-height: 1; }}
    .skor-signal-kuat {{ color: var(--red); }}
    .skor-radar {{ color: var(--orange); }}
    .skor-pantau {{ color: var(--yellow); }}
    .skor-noise {{ color: var(--gray); }}
    .skor-verdict {{ font-size: 0.85rem; font-weight: 600; color: var(--muted); }}

    .detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    @media (max-width: 600px) {{ .detail-grid {{ grid-template-columns: 1fr; }} }}
    .detail-col-title {{ font-size: 0.78rem; font-weight: 700; color: var(--muted);
                          text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px; }}

    /* Breakdown bars */
    .bar-row {{ display: flex; align-items: center; gap: 6px; margin-bottom: 5px; font-size: 0.78rem; }}
    .bar-label {{ width: 110px; flex-shrink: 0; color: var(--muted); }}
    .bar-track {{ flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 3px; transition: width .4s; }}
    .bar-fill-signal-kuat {{ background: var(--red); }}
    .bar-fill-radar {{ background: var(--orange); }}
    .bar-fill-pantau {{ background: var(--yellow); }}
    .bar-fill-noise {{ background: var(--gray); }}
    .bar-val {{ width: 36px; text-align: right; color: var(--muted); font-size: 0.72rem; }}

    /* Highlight */
    .highlight-text {{ font-size: 0.85rem; color: var(--text); line-height: 1.5;
                        padding: 8px 12px; background: #f8fafc; border-radius: 6px;
                        border-left: 3px solid #cbd5e1; }}

    /* Deep analysis */
    .deep-row {{ display: flex; gap: 10px; margin-bottom: 10px; font-size: 0.82rem; }}
    .deep-label {{ width: 120px; flex-shrink: 0; font-weight: 600; color: var(--muted);
                   font-size: 0.75rem; padding-top: 2px; }}
    .deep-val {{ flex: 1; color: var(--text); }}
    .deep-list {{ list-style: disc; padding-left: 16px; }}
    .deep-list li {{ margin-bottom: 3px; }}
    .risk-list {{ color: #dc2626; }}

    /* Footer */
    .site-footer {{ background: #0f172a; color: #94a3b8; text-align: center;
                    padding: 16px; font-size: 0.8rem; margin-top: 40px; }}
  </style>
</head>
<body>

<header class="site-header">
  <div class="container">
    <div class="site-title">📊 Market Scan IDX</div>
    <div class="site-meta">
      {tgl_str}<br>
      <span style="color:#64748b;">Diproses {jam_str}</span>
    </div>
  </div>
</header>

<div class="container">
  {stats_html}
  {sec_signal}
  {sec_radar}
  {sec_pantau}
  {sec_noise}
</div>

<footer class="site-footer">
  Market Scan IDX — Powered by Claude AI &nbsp;|&nbsp; {tgl_str}
</footer>

<script>
function toggleDetail(id, btn) {{
  const el = document.getElementById(id);
  if (!el) return;
  const isHidden = el.style.display === 'none' || el.style.display === '';
  el.style.display = isHidden ? 'block' : 'none';
  const ico = btn.querySelector('.ico');
  if (ico) ico.style.transform = isHidden ? 'rotate(180deg)' : '';
}}
</script>

</body>
</html>"""


def save_html(results: list, config: dict, run_time: str) -> str:
    """Simpan HTML ke folder output dan return path-nya."""
    output_dir = os.path.join(BASE_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)

    try:
        dt       = datetime.fromisoformat(run_time)
        filename = dt.strftime("%Y-%m-%d_%H%M") + ".html"
    except Exception:
        filename = "scan_latest.html"

    html_path = os.path.join(output_dir, filename)
    html      = build_html(results, config, run_time)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    log.info("HTML disimpan: %s (%d chars)", html_path, len(html))
    return html_path
