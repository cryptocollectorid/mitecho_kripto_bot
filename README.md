# Crypto Analysis Telegram Bot (GitHub Actions)

Automated fundamental + technical analysis + futures signals for crypto (day & swing trading focus).

Posts scheduled reports to your Telegram channel.

**Disclaimer**: Not financial advice. Markets are risky. DYOR. This is a template.

## Setup Steps (Detailed)

### 1. Create Telegram Bot
1. Open Telegram, search @BotFather
2. Send `/newbot`
3. Follow instructions, get **Bot Token** (e.g. `123456:ABC-DEF...`)
4. (Optional) Set bot description, etc.

### 2. Create Telegram Channel
1. Create a new Channel (public or private)
2. Add your bot as **Administrator** (with post permission)
3. Get Chat ID:
   - For public: use `@channelusername`
   - For private/group: Send a message to the channel, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` and look for `"chat":{"id":-100xxxxxxxxxx}`

### 3. Create GitHub Repository
1. Create new public/private repo on GitHub
2. Upload these files:
   - `requirements.txt`
   - `src/analysis_bot.py`
   - `.github/workflows/crypto_analysis.yml`
3. Or clone and push the structure.

### 4. Add Repository Secrets
Go to Repo → Settings → Secrets and variables → Actions → New repository secret

Add:
- `TELEGRAM_BOT_TOKEN`: your bot token
- `TELEGRAM_CHAT_ID`: your channel chat id
- Optional:
  - `COINGECKO_API_KEY` (from coingecko.com/api)
  - `CMC_API_KEY` (pro.coinmarketcap.com)
  - `NANSEN_API_KEY` (nansen.ai - paid plan)
  - `ARKHAM_API_KEY` (arkm.com - request access, paid)

### 5. Enable GitHub Actions
- Push the files
- Go to Actions tab, enable if needed
- Workflow will run on schedule or you can trigger manually via "Run workflow"

### 6. Customize
- Edit `COINS` list in `analysis_bot.py`
- Adjust thesis/signal logic
- Change cron schedule in workflow YAML (UTC)
- Add more data sources (Nansen smart money, Arkham entity flows)
- Integrate TradingView webhooks or more TA indicators
- For CMC: use their latest quotes endpoint
- Add charts by generating images (matplotlib) and send as photo

### Data Sources Notes
- **CoinGecko**: Free public API (rate limited) or Demo/Pro key. Good for prices, mcap, community.
- **CoinMarketCap**: Free Basic plan available. Similar market data.
- **Nansen**: On-chain smart money, whale flows, PnL. Requires paid subscription + API key. Endpoints for netflow, holdings, perp trades.
- **Arkham**: Entity labeling, address intelligence, transfers. Paid API, request access.
- **Binance Futures**: Public endpoints for funding, OI, long/short ratio, klines – no key needed for market data.

### Scheduling Tips
- Day trading: every 1-4 hours
- Swing: 1-2 times per day
- GitHub Actions free tier: 2000 minutes/month for private, unlimited for public.

### Testing Locally
```bash
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
pip install -r requirements.txt
python src/analysis_bot.py
```

Extend the script for full FA (tokenomics, team, news via other APIs), more TA timeframes, risk management rules, etc.

Happy trading – but manage risk!
