"""
Crypto Analysis Bot - Fundamental + Technical + Futures Signals
Untuk Day Trading & Swing Trading
Dijalankan via GitHub Actions → Telegram Channel

Disclaimer: Bukan nasihat keuangan. DYOR. Risiko kehilangan modal tinggi.
"""

import os
import sys
import time
import yaml
import requests
import pandas as pd
import ta
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

COINS = CONFIG.get("coins", ["bitcoin"])
SETTINGS = CONFIG.get("settings", {})
SIGNALS = CONFIG.get("signals", {})

# Environment variables (GitHub Secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
CMC_API_KEY = os.getenv("CMC_API_KEY")
NANSEN_API_KEY = os.getenv("NANSEN_API_KEY")
ARKHAM_API_KEY = os.getenv("ARKHAM_API_KEY")

CG_BASE = "https://api.coingecko.com/api/v3"
BINANCE_FUTURES = "https://fapi.binance.com"
CMC_BASE = "https://pro-api.coinmarketcap.com/v1"

def request_with_retry(url: str, params: dict = None, headers: dict = None, max_retries: int = 3) -> Optional[dict]:
    """Request dengan retry sederhana."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            else:
                print(f"HTTP {resp.status_code} for {url}")
        except Exception as e:
            print(f"Request error: {e}")
            time.sleep(1)
    return None

def get_global_data() -> Dict[str, Any]:
    """Data global market dari CoinGecko."""
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
    data = request_with_retry(f"{CG_BASE}/global", headers=headers)
    if not data or "data" not in data:
        return {}
    d = data["data"]
    return {
        "total_market_cap": d.get("total_market_cap", {}).get("usd"),
        "total_volume": d.get("total_volume", {}).get("usd"),
        "btc_dominance": d.get("market_cap_percentage", {}).get("btc"),
        "eth_dominance": d.get("market_cap_percentage", {}).get("eth"),
        "market_cap_change_24h": d.get("market_cap_change_percentage_24h_usd"),
        "active_cryptos": d.get("active_cryptocurrencies"),
    }

def get_coingecko_coin(coin_id: str) -> Dict[str, Any]:
    """Detail coin dari CoinGecko."""
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY
    params = {
        "localization": "false",
        "tickers": "false",
        "market_data": "true",
        "community_data": "true",
        "developer_data": "false",
        "sparkline": "false"
    }
    data = request_with_retry(f"{CG_BASE}/coins/{coin_id}", params=params, headers=headers)
    if not data:
        return {}
    market = data.get("market_data", {})
    return {
        "id": coin_id,
        "name": data.get("name"),
        "symbol": data.get("symbol", "").upper(),
        "price": market.get("current_price", {}).get("usd"),
        "market_cap": market.get("market_cap", {}).get("usd"),
        "volume_24h": market.get("total_volume", {}).get("usd"),
        "change_24h": market.get("price_change_percentage_24h"),
        "change_7d": market.get("price_change_percentage_7d"),
        "change_30d": market.get("price_change_percentage_30d"),
        "ath": market.get("ath", {}).get("usd"),
        "ath_change": market.get("ath_change_percentage", {}).get("usd"),
        "circulating": market.get("circulating_supply"),
        "total_supply": market.get("total_supply"),
        "max_supply": market.get("max_supply"),
        "sentiment_up": data.get("sentiment_votes_up_percentage"),
        "sentiment_down": data.get("sentiment_votes_down_percentage"),
        "description": (data.get("description", {}).get("en") or "")[:300],
    }

def get_binance_futures(symbol: str) -> Dict[str, Any]:
    """Data futures publik dari Binance."""
    result = {}
    # Premium index (funding + mark price)
    prem = request_with_retry(f"{BINANCE_FUTURES}/fapi/v1/premiumIndex", {"symbol": symbol})
    if prem:
        result["funding_rate"] = float(prem.get("lastFundingRate", 0)) * 100  # dalam %
        result["mark_price"] = float(prem.get("markPrice", 0))
        result["index_price"] = float(prem.get("indexPrice", 0))

    # Open Interest
    oi = request_with_retry(f"{BINANCE_FUTURES}/fapi/v1/openInterest", {"symbol": symbol})
    if oi:
        result["open_interest"] = float(oi.get("openInterest", 0))

    # Long/Short Account Ratio
    ls = request_with_retry(
        f"{BINANCE_FUTURES}/futures/data/globalLongShortAccountRatio",
        {"symbol": symbol, "period": "5m", "limit": 1}
    )
    if ls and isinstance(ls, list) and len(ls) > 0:
        result["long_short_ratio"] = float(ls[0].get("longShortRatio", 0))

    # Klines 1h untuk TA
    klines = request_with_retry(
        f"{BINANCE_FUTURES}/fapi/v1/klines",
        {"symbol": symbol, "interval": "1h", "limit": 120}
    )
    result["klines"] = klines or []
    return result

def compute_technicals(klines: List) -> Dict[str, Any]:
    """Hitung indikator teknikal sederhana."""
    if not klines or len(klines) < 50:
        return {"error": "Data klines tidak cukup"}
    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"
    ])
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd_ind = ta.trend.MACD(df["close"])
    df["macd"] = macd_ind.macd()
    df["macd_signal"] = macd_ind.macd_signal()
    df["macd_hist"] = macd_ind.macd_diff()
    df["ema20"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(df["close"], window=200).ema_indicator()

    last = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_val = round(last["rsi"], 2) if pd.notna(last["rsi"]) else None
    trend = "Bullish" if last["close"] > last["ema20"] > last["ema50"] else \
             "Bearish" if last["close"] < last["ema20"] < last["ema50"] else "Neutral/Sideways"

    macd_cross = "Bullish Cross" if (prev["macd"] < prev["macd_signal"] and last["macd"] > last["macd_signal"]) else \
                 "Bearish Cross" if (prev["macd"] > prev["macd_signal"] and last["macd"] < last["macd_signal"]) else "No Cross"

    return {
        "price": round(last["close"], 2),
        "rsi": rsi_val,
        "rsi_status": "Oversold" if rsi_val and rsi_val < SIGNALS.get("rsi_oversold", 30) else
                      "Overbought" if rsi_val and rsi_val > SIGNALS.get("rsi_overbought", 70) else "Neutral",
        "macd": round(last["macd"], 4) if pd.notna(last["macd"]) else None,
        "macd_signal": round(last["macd_signal"], 4) if pd.notna(last["macd_signal"]) else None,
        "macd_cross": macd_cross,
        "ema20": round(last["ema20"], 2),
        "ema50": round(last["ema50"], 2),
        "trend": trend,
        "volume": round(last["volume"], 2),
    }

def generate_thesis(cg: Dict, futures: Dict, ta_data: Dict) -> str:
    """Generate thesis sederhana berdasarkan data."""
    change_24h = cg.get("change_24h") or 0
    funding = futures.get("funding_rate") or 0
    ls_ratio = futures.get("long_short_ratio") or 1
    trend = ta_data.get("trend", "Neutral")

    if change_24h > 3 and funding > SIGNALS.get("funding_high", 0.01) and ls_ratio > SIGNALS.get("long_short_crowded", 1.8):
        return "Cautious Bullish - Hati-hati long crowding. Cocok swing dengan stop ketat."
    elif change_24h < -3 and funding < SIGNALS.get("funding_low", -0.005):
        return "Potential Bounce / Short Squeeze. Pantau konfirmasi teknikal."
    elif trend == "Bullish" and ta_data.get("rsi_status") == "Neutral":
        return "Bullish Bias - Trend naik, RSI sehat. Cocok day & swing long."
    elif trend == "Bearish":
        return "Bearish Bias - Hindari long agresif. Fokus short atau tunggu reversal."
    else:
        return "Neutral / Range-bound. Cocok day trading range, hindari breakout palsu."

def generate_futures_signal(futures: Dict) -> str:
    funding = futures.get("funding_rate") or 0
    ls = futures.get("long_short_ratio") or 1
    if funding > SIGNALS.get("funding_high", 0.01) and ls > SIGNALS.get("long_short_crowded", 1.8):
        return "⚠️ Long Crowding Risk - Potensi liquidation cascade"
    elif funding < SIGNALS.get("funding_low", -0.005):
        return "🟢 Short Squeeze Potential - Shorts bayar longs"
    elif funding > 0:
        return "Mild Bullish (Longs bayar shorts)"
    else:
        return "Neutral / Mild Bearish"

def format_message(cg: Dict, futures: Dict, ta_data: Dict, global_data: Dict) -> str:
    """Format pesan Telegram (Markdown)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    thesis = generate_thesis(cg, futures, ta_data)
    fut_signal = generate_futures_signal(futures)

    price = cg.get("price") or 0
    ath = cg.get("ath") or 0
    from_ath = ((price / ath) - 1) * 100 if ath else 0

    msg = f"""
📊 *{cg.get('name')} ({cg.get('symbol')})* | {now}

🎯 *THESIS*
{thesis}
_Metode: Day Trading + Swing Trading | Bukan financial advice. DYOR._

📈 *FUNDAMENTAL* (CoinGecko)
• Price: ${price:,.2f} | 24h: {cg.get('change_24h') or 0:+.2f}% | 7d: {cg.get('change_7d') or 0:+.2f}%
• Market Cap: ${ (cg.get('market_cap') or 0)/1e9 :.2f}B
• Volume 24h: ${ (cg.get('volume_24h') or 0)/1e9 :.2f}B
• ATH: ${ath:,.0f} ({from_ath:+.1f}% dari ATH)
• Circulating: {(cg.get('circulating') or 0)/1e6:.2f}M
• Sentiment: {cg.get('sentiment_up') or 'N/A'}% Bullish

📊 *TEKNIKAL (1H)*
• Price: ${ta_data.get('price')}
• RSI(14): {ta_data.get('rsi')} ({ta_data.get('rsi_status')})
• MACD: {ta_data.get('macd')} / Signal {ta_data.get('macd_signal')} → {ta_data.get('macd_cross')}
• EMA20: ${ta_data.get('ema20')} | EMA50: ${ta_data.get('ema50')}
• Trend: {ta_data.get('trend')}

⚡ *FUTURES SIGNALS* (Binance {cg.get('symbol')}USDT)
• Funding Rate: {futures.get('funding_rate', 0):+.4f}% (per 8h)
• Open Interest: {futures.get('open_interest', 0):,.0f}
• Long/Short Ratio: {futures.get('long_short_ratio', 'N/A')}
• Sinyal: {fut_signal}

🌐 *Global*: Total MCap ${ (global_data.get('total_market_cap') or 0)/1e12 :.2f}T | BTC Dom {global_data.get('btc_dominance', 0):.1f}%

#Crypto #Analysis #{cg.get('symbol')}
"""
    return msg.strip()

def send_telegram(text: str) -> bool:
    """Kirim pesan ke Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID tidak ditemukan")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4090],  # Telegram limit
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            print("✓ Pesan terkirim")
            return True
        else:
            print(f"✗ Gagal kirim: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"✗ Exception kirim Telegram: {e}")
        return False

def main():
    print("=== Memulai Crypto Analysis Bot ===")
    global_data = get_global_data()
    print(f"Global data fetched: BTC Dom {global_data.get('btc_dominance')}")

    if SETTINGS.get("include_global_summary") and global_data:
        summary = f"""
🌐 *GLOBAL CRYPTO MARKET UPDATE*
{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

• Total Market Cap: ${ (global_data.get('total_market_cap') or 0)/1e12 :.2f}T ({global_data.get('market_cap_change_24h') or 0:+.2f}% 24h)
• Total Volume 24h: ${ (global_data.get('total_volume') or 0)/1e9 :.1f}B
• BTC Dominance: {global_data.get('btc_dominance', 0):.2f}%
• ETH Dominance: {global_data.get('eth_dominance', 0):.2f}%
• Active Cryptos: {global_data.get('active_cryptos', 'N/A')}

_Data: CoinGecko | Analisis otomatis via GitHub Actions_
"""
        send_telegram(summary.strip())
        time.sleep(1)

    for coin_id in COINS:
        print(f"\n--- Processing {coin_id} ---")
        try:
            cg = get_coingecko_coin(coin_id)
            if not cg.get("symbol"):
                print(f"Skip {coin_id}: data tidak lengkap")
                continue
            symbol = f"{cg['symbol']}USDT"
            futures = get_binance_futures(symbol)
            ta_data = compute_technicals(futures.get("klines", []))
            message = format_message(cg, futures, ta_data, global_data)
            send_telegram(message)
            time.sleep(2)  # Hindari rate limit Telegram
        except Exception as e:
            print(f"Error pada {coin_id}: {e}")
            send_telegram(f"⚠️ Error analisis *{coin_id}*: {str(e)[:300]}")

    print("=== Selesai ===")

if __name__ == "__main__":
    main()
