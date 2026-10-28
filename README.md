# Crypto Analysis Bot ADVANCED

Versi lebih lengkap dengan:

- Chart candlestick + EMA otomatis
- Multi-timeframe (15m, 1h, 4h, 1d)
- Ranking Top Gainers & Losers
- Nansen dummy (siap diganti real API)
- Futures signals + Thesis

## Setup

1. Upload semua file ke GitHub repo
2. Isi Secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - Opsional: `COINGECKO_API_KEY`, `NANSEN_API_KEY`
3. Jalankan workflow manual atau tunggu jadwal

## Struktur

```
crypto-advanced/
├── .github/workflows/advanced_analysis.yml
├── config/config.yaml
├── src/analysis_bot.py
└── requirements.txt
```

## Catatan Chart

Chart dikirim sebagai foto ke Telegram. Pastikan bot punya izin kirim media.

Untuk Nansen asli, set `use_real_api: true` di config dan isi secret `NANSEN_API_KEY`.
