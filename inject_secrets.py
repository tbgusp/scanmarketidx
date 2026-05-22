"""
inject_secrets.py
Inject semua secret dari environment variable ke config.json saat runtime.
Dijalankan SEBELUM main.py di GitHub Actions.

Secret TIDAK PERNAH disimpan di file — hanya ada di GitHub Secrets
dan diinjek ke memory (config.json sementara) saat job berjalan.
"""

import json
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

REQUIRED = {
    "ANTHROPIC_API_KEY":  "anthropic_api_key",
    "GITHUB_TOKEN_SCAN":  "github.token",
    "TELEGRAM_BOT_TOKEN": "telegram.bot_token",
    "TELEGRAM_CHANNEL_ID":"telegram.channel_id",
}


def set_nested(d: dict, dotted_key: str, value: str):
    """Set nilai dengan key bertingkat pakai dot notation."""
    keys = dotted_key.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def inject():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)

    missing = []
    for env_key, cfg_key in REQUIRED.items():
        val = os.environ.get(env_key, "").strip()
        if val:
            set_nested(cfg, cfg_key, val)
            print(f"[inject] ✓ {env_key} → config.{cfg_key}")
        else:
            missing.append(env_key)
            print(f"[inject] ✗ {env_key} tidak ditemukan di environment!")

    if missing:
        print(f"\n[inject] ERROR: {len(missing)} secret tidak ada: {missing}")
        print("[inject] Pastikan semua secret sudah ditambahkan di:")
        print("[inject] GitHub repo → Settings → Secrets and variables → Actions")
        sys.exit(1)

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

    print("[inject] config.json berhasil diupdate dengan semua secret.")


if __name__ == "__main__":
    inject()
