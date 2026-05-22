# 📊 Market Scan IDX

Scan otomatis berita saham IDX dari 8 sumber, dianalisis Claude AI,
hasil dikirim ke Telegram Channel setiap jam 06:00 WIB.

**Hasil scan:** https://tbgusp.github.io/scanmarketidx/

---

## Sumber Berita
| Source | Metode |
|--------|--------|
| CNBC Indonesia | max 30 artikel |
| Bloomberg Technoz | 3 hari ke belakang, max 30 |
| IDX Channel | max 30 artikel |
| IDN Financials | max 30 artikel |
| Emiten News | max 30 artikel |
| Investor.ID | max 30 artikel |
| Kontan | 3 hari ke belakang, max 30 |
| Liputan6 | 3 hari via RSS, max 30 |

## Cara Kerja
1. GitHub Actions jalan jam 06:00 WIB (Senin–Jumat)
2. Scrape artikel baru dari 8 sumber
3. Screening dengan Claude Haiku (semua artikel)
4. Deep analysis dengan Claude Sonnet (artikel skor tinggi)
5. Upload HTML ke GitHub Pages
6. Kirim link ke Telegram Channel

## Setup
Lihat [SETUP_GUIDE.md](SETUP_GUIDE.md)
