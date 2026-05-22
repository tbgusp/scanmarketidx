"""
publisher_github.py
Upload file HTML hasil scan ke GitHub Pages via GitHub API.
Setiap scan disimpan sebagai scan/YYYY-MM-DD.html
Index terbaru disimpan sebagai index.html (redirect otomatis ke scan terbaru)

GitHub Pages URL: https://tbgusp.github.io/scanmarketidx/scan/YYYY-MM-DD.html
"""

import base64
import json
import logging
import os
import requests
from datetime import datetime

log = logging.getLogger(__name__)

GITHUB_API   = "https://api.github.com"
REPO_OWNER   = "tbgusp"
REPO_NAME    = "scanmarketidx"
BRANCH       = "main"
PAGES_BASE   = f"https://{REPO_OWNER}.github.io/{REPO_NAME}"


def _get_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-11-28",
        "Content-Type":  "application/json",
    }


def _get_file_sha(token: str, path: str) -> str | None:
    """Ambil SHA file yang sudah ada di repo (diperlukan untuk update)."""
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
    try:
        resp = requests.get(url, headers=_get_headers(token), timeout=15)
        if resp.status_code == 200:
            return resp.json().get("sha")
        return None
    except Exception:
        return None


def _upload_file(token: str, path: str, content: str, commit_msg: str) -> bool:
    """
    Upload atau update satu file ke GitHub repo via Contents API.
    content: string teks (akan di-encode base64 otomatis)
    """
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"

    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    payload = {
        "message": commit_msg,
        "content": encoded,
        "branch":  BRANCH,
    }

    # Kalau file sudah ada, sertakan SHA untuk update (bukan create baru)
    existing_sha = _get_file_sha(token, path)
    if existing_sha:
        payload["sha"] = existing_sha

    try:
        resp = requests.put(url, headers=_get_headers(token),
                            data=json.dumps(payload), timeout=30)
        if resp.status_code in (200, 201):
            log.info("[GitHub] Upload sukses: %s", path)
            return True
        else:
            log.error("[GitHub] Upload gagal %s: %s — %s", path,
                      resp.status_code, resp.text[:300])
            return False
    except Exception as e:
        log.error("[GitHub] Exception upload %s: %s", path, e)
        return False


def _build_index_html(scan_date: str, scan_url: str) -> str:
    """Buat index.html yang auto-redirect ke scan terbaru."""
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url={scan_url}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Market Scan IDX — {scan_date}</title>
  <style>
    body {{ font-family: sans-serif; background: #0d1117; color: #c9d1d9;
            display: flex; align-items: center; justify-content: center;
            height: 100vh; margin: 0; }}
    a {{ color: #58a6ff; }}
  </style>
</head>
<body>
  <p>Mengarahkan ke scan terbaru... <a href="{scan_url}">klik di sini</a></p>
</body>
</html>"""


def publish_to_github(html_content: str, config: dict, run_time: str) -> str | None:
    """
    Upload HTML ke GitHub Pages.
    Return: URL publik file HTML, atau None jika gagal.
    """
    gh_cfg = config.get("github", {})
    token  = gh_cfg.get("token", "")

    if not token or token == "GITHUB_TOKEN_DISINI":
        log.warning("[GitHub] github.token belum diisi di config.json — skip publish.")
        return None

    # Tentukan nama file berdasarkan tanggal scan
    try:
        dt = datetime.fromisoformat(run_time)
    except Exception:
        dt = datetime.now()

    date_str  = dt.strftime("%Y-%m-%d")
    file_path = f"scan/{date_str}.html"
    scan_url  = f"{PAGES_BASE}/{file_path}"

    # Upload file scan harian
    ok_scan = _upload_file(
        token      = token,
        path       = file_path,
        content    = html_content,
        commit_msg = f"scan: {date_str} market scan result",
    )

    if not ok_scan:
        log.error("[GitHub] Gagal upload scan HTML.")
        return None

    # Update index.html → redirect ke scan terbaru
    index_html = _build_index_html(date_str, scan_url)
    _upload_file(
        token      = token,
        path       = "index.html",
        content    = index_html,
        commit_msg = f"index: update redirect ke {date_str}",
    )

    log.info("[GitHub] Scan dipublikasikan: %s", scan_url)
    return scan_url
