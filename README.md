# Crypto Analysis Bot (Fundamental + Technical + Futures)

Bot otomatis yang melakukan analisis kripto lengkap (Thesis, Fundamental, Teknikal, dan Sinyal Futures) lalu mengirimkannya secara terjadwal ke Telegram Channel menggunakan **GitHub Actions**.

Cocok untuk metode **Day Trading** dan **Swing Trading**.

> ⚠️ **Disclaimer**: Ini bukan nasihat keuangan. Trading kripto berisiko tinggi kehilangan seluruh modal. Lakukan riset sendiri (DYOR), gunakan manajemen risiko yang ketat, dan hanya trade dengan uang yang siap hilang.

---

## Fitur

- Data real-time dari **CoinGecko** (harga, market cap, volume, sentiment)
- Data **Binance Futures** publik (Funding Rate, Open Interest, Long/Short Ratio, Klines)
- Analisis Teknikal otomatis (RSI, MACD, EMA 20/50, Trend)
- Thesis & Futures Signal otomatis
- Dukungan opsional: CoinMarketCap, Nansen, Arkham (jika API key tersedia)
- Kirim ke Telegram Channel secara terjadwal
- Gratis (GitHub Actions free tier)
- Mudah dikustomisasi lewat `config/config.yaml`

---

## Struktur Repository

```
crypto-analysis-repo/
├── .github/
│   └── workflows/
│       └── crypto_analysis.yml     # Workflow GitHub Actions
├── config/
│   └── config.yaml                 # Daftar coin & pengaturan
├── src/
│   └── analysis_bot.py             # Script utama
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Langkah Setup Lengkap (Bahasa Indonesia)

### 1. Buat Telegram Bot
1. Buka Telegram dan cari **@BotFather**.
2. Kirim perintah `/newbot`.
3. Ikuti instruksi (beri nama & username bot).
4. Simpan **Bot Token** yang diberikan (contoh: `7123456789:AAHxxxxxxxx`).

### 2. Buat Channel Telegram
1. Buat Channel baru (bisa publik atau privat).
2. Tambahkan bot kamu sebagai **Administrator**.
3. Berikan izin untuk mengirim pesan (Post Messages).
4. Dapatkan **Chat ID**:
   - Jika channel publik: gunakan `@nama_channel`
   - Jika privat: kirim pesan ke channel, lalu buka browser:
     ```
     https://api.telegram.org/bot<TOKEN_KAMU>/getUpdates
     ```
     Cari `"chat":{"id":-100xxxxxxxxxx}` dan salin angkanya.

### 3. Upload ke GitHub
1. Buat repository baru di GitHub (public lebih disarankan agar free minutes unlimited).
2. Upload semua file dari folder ini ke repository tersebut.
   - Atau clone repo kosong lalu copy file-file ini.

### 4. Tambahkan Secrets
Pergi ke:
**Repository → Settings → Secrets and variables → Actions → New repository secret**

Tambahkan secret berikut:

| Nama Secret          | Wajib? | Keterangan                          |
|----------------------|--------|-------------------------------------|
| `TELEGRAM_BOT_TOKEN` | Ya     | Token dari BotFather                |
| `TELEGRAM_CHAT_ID`   | Ya     | Chat ID channel                     |
| `COINGECKO_API_KEY`  | Opsional | API key CoinGecko (Demo/Pro)     |
| `CMC_API_KEY`        | Opsional | API key CoinMarketCap            |
| `NANSEN_API_KEY`     | Opsional | API key Nansen (berbayar)        |
| `ARKHAM_API_KEY`     | Opsional | API key Arkham (berbayar)        |

### 5. Aktifkan Workflow
1. Push semua file.
2. Buka tab **Actions** di repository.
3. Jika ada peringatan, klik "I understand my workflows, go ahead and enable them".
4. Workflow akan berjalan sesuai jadwal cron.
5. Untuk testing: klik workflow → **Run workflow** → Run.

### 6. Kustomisasi
- Ubah daftar coin di `config/config.yaml`
- Ubah jadwal di file `.github/workflows/crypto_analysis.yml` (format cron UTC)
- Sesuaikan threshold sinyal di `config.yaml`
- Tambahkan logika thesis atau indikator teknikal di `src/analysis_bot.py`

---

## Contoh Jadwal Cron (UTC)

| Kebutuhan              | Cron Expression     | Keterangan                  |
|------------------------|---------------------|-----------------------------|
| Setiap 4 jam           | `0 */4 * * *`      | Default                     |
| Setiap jam (Day Trade) | `0 * * * *`        | Lebih sering                |
| 2x sehari (Swing)      | `0 8,20 * * *`     | Pagi & malam                |
| Setiap hari jam 7 pagi | `0 7 * * *`        | Satu kali sehari            |

---

## Testing Lokal

```bash
# Buat file .env (jangan di-commit)
echo "TELEGRAM_BOT_TOKEN=xxx" > .env
echo "TELEGRAM_CHAT_ID=xxx" >> .env

# Install & jalankan
pip install -r requirements.txt
python src/analysis_bot.py
```

---

## Catatan Sumber Data

- **CoinGecko**: Gratis (rate limit ketat). Lebih baik pakai API key.
- **Binance Futures**: Publik, tidak butuh key untuk data market.
- **CoinMarketCap**: Free Basic plan tersedia.
- **Nansen**: On-chain smart money, whale activity. Berbayar.
- **Arkham**: Entity labeling & transfer intelligence. Berbayar / request access.

---

## Pengembangan Lanjutan

- Tambahkan chart (matplotlib + sendPhoto)
- Integrasi berita (CryptoPanic, NewsAPI)
- Multi-timeframe (4H, Daily)
- Risk management calculator
- Ranking top movers
- Dukungan exchange lain (Bybit, OKX)

---

**Selamat menggunakan!** Kelola risiko dengan baik.  
Jika ada error, cek tab Actions → log workflow.

*Dibuat sebagai template edukasi. Bukan rekomendasi investasi.*
