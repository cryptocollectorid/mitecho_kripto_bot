"""
Crypto Analysis Bot for Telegram via GitHub Actions
Fetches data from CoinGecko, Binance Futures, and optional CMC/Nansen/Arkham.
Generates Fundamental + Technical analysis + Futures signals.
Not financial advice.
"""

import os
import requests
import json
from datetime import datetime
import pandas as pd
import ta

# Secrets from environment (GitHub Actions secrets)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # e.g. @yourchannel or -100xxxxxxxxxx
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")  # optional for pro
CMC_API_KEY = os.getenv("CMC_API_KEY")  # optional
NANSEN_API_KEY = os.getenv("NANSEN_API_KEY")  # optional, paid
ARKHAM_API_KEY = os.getenv("ARKHAM_API_KEY")  # optional, paid

# Coins to analyze (CoinGecko IDs)
COINS = ["bitcoin", "ethereum", "solana"]  # extend as needed

def get_coingecko_data(coin_id: str):
    """Fetch market data from CoinGecko (public or with key)."""
    base_url = "https://api.coingecko.com/api/v3"
    headers = {}
    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY  # or pro header
    
    # Global
    global_resp = requests.get(f"{base_url}/global", headers=headers, timeout=10)
    global_data = global_resp.json().get("data", {})
    
    # Coin specific
    coin_resp = requests.get(
        f"{base_url}/coins/{coin_id}",
        params={"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"},
        headers=headers,
        timeout=10
    )
    coin_data = coin_resp.json()
    
    market = coin_data.get("market_data", {})
    return {
        "name": coin_data.get("name"),
        "symbol": coin_data.get("symbol", "").upper(),
        "price": market.get("current_price", {}).get("usd"),
        "market_cap": market.get("market_cap", {}).get("usd"),
        "volume_24h": market.get("total_volume", {}).get("usd"),
        "change_24h": market.get("price_change_percentage_24h"),
        "change_7d": market.get("price_change_percentage_7d"),
        "ath": market.get("ath", {}).get("usd"),
        "circulating": market.get("circulating_supply"),
        "global_mcap": global_data.get("total_market_cap", {}).get("usd"),
        "btc_dominance": global_data.get("market_cap_percentage", {}).get("btc"),
        "sentiment_up": coin_data.get("sentiment_votes_up_percentage"),
    }

def get_binance_futures_data(symbol: str = "BTCUSDT"):
    """Fetch public futures data from Binance."""
    base = "https://fapi.binance.com"
    
    # Funding rate
    funding = requests.get(f"{base}/fapi/v1/premiumIndex", params={"symbol": symbol}, timeout=10).json()
    
    # Open Interest
    oi = requests.get(f"{base}/fapi/v1/openInterest", params={"symbol": symbol}, timeout=10).json()
    
    # Long/Short ratio (global accounts)
    ls = requests.get(
        f"{base}/futures/data/globalLongShortAccountRatio",
        params={"symbol": symbol, "period": "5m", "limit": 1},
        timeout=10
    ).json()
    
    # Recent klines for TA (1h)
    klines = requests.get(
        f"{base}/fapi/v1/klines",
        params={"symbol": symbol, "interval": "1h", "limit": 100},
        timeout=10
    ).json()
    
    return {
        "funding_rate": float(funding.get("lastFundingRate", 0)) * 100,  # in %
        "mark_price": float(funding.get("markPrice", 0)),
        "open_interest": float(oi.get("openInterest", 0)),
        "long_short_ratio": float(ls[0]["longShortRatio"]) if ls else None,
        "klines": klines,
    }

def compute_technicals(klines):
    """Simple TA using pandas and ta library."""
    if not klines:
        return {}
    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "taker_base", "taker_quote", "ignore"
    ])
    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["volume"] = df["volume"].astype(float)
    
    # Indicators
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["ema20"] = ta.trend.EMAIndicator(df["close"], window=20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()
    
    last = df.iloc[-1]
    return {
        "rsi": round(last["rsi"], 2) if pd.notna(last["rsi"]) else None,
        "macd": round(last["macd"], 4) if pd.notna(last["macd"]) else None,
        "macd_signal": round(last["macd_signal"], 4) if pd.notna(last["macd_signal"]) else None,
        "ema20": round(last["ema20"], 2),
        "ema50": round(last["ema50"], 2),
        "price": round(last["close"], 2),
        "trend": "Bullish" if last["close"] > last["ema20"] > last["ema50"] else "Bearish" if last["close"] < last["ema20"] < last["ema50"] else "Neutral",
    }

def generate_analysis(coin_id: str):
    """Generate full analysis message."""
    cg = get_coingecko_data(coin_id)
    symbol = f"{cg['symbol']}USDT"
    futures = get_binance_futures_data(symbol)
    ta_data = compute_technicals(futures["klines"])
    
    # Thesis based on simple rules (customize heavily)
    thesis = "Neutral / Range-bound"
    if cg["change_24h"] and cg["change_24h"] > 2 and futures["funding_rate"] > 0.01:
        thesis = "Cautious Bullish (overheated longs)"
    elif cg["change_24h"] and cg["change_24h"] < -2 and futures["funding_rate"] < 0:
        thesis = "Potential Bounce (shorts paying)"
    
    # Futures signal
    futures_signal = "Neutral"
    if futures["funding_rate"] > 0.01 and futures.get("long_short_ratio", 1) > 1.5:
        futures_signal = "Long Crowding Risk - Watch for liquidation cascade"
    elif futures["funding_rate"] < -0.005:
        futures_signal = "Short Squeeze Potential"
    
    # Format message (Telegram supports Markdown)
    msg = f"""
📊 *{cg['name']} ({cg['symbol']}) Analysis* - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

🎯 *Thesis*: {thesis}
_Metode: Day + Swing Trading framework. Bukan financial advice. DYOR._

📈 *Fundamental*
• Price: ${cg['price']:,.2f} ({cg['change_24h']:+.2f}% 24h | {cg['change_7d']:+.2f}% 7d)
• Market Cap: ${cg['market_cap']/1e9:.1f}B
• Volume 24h: ${cg['volume_24h']/1e9:.1f}B
• ATH: ${cg['ath']:,.0f} ({((cg['price']/cg['ath']-1)*100):+.1f}% from ATH)
• Circulating: {cg['circulating']/1e6:.1f}M
• BTC Dominance: {cg['btc_dominance']:.1f}% | Total MCap: ${cg['global_mcap']/1e12:.2f}T
• Sentiment: {cg.get('sentiment_up', 'N/A')}% bullish

📊 *Technical (1H)*
• Price: ${ta_data.get('price')}
• RSI(14): {ta_data.get('rsi')} ({'Oversold' if ta_data.get('rsi') and ta_data['rsi']<30 else 'Overbought' if ta_data.get('rsi') and ta_data['rsi']>70 else 'Neutral'})
• MACD: {ta_data.get('macd')} / Signal {ta_data.get('macd_signal')}
• EMA20: ${ta_data.get('ema20')} | EMA50: ${ta_data.get('ema50')}
• Trend: {ta_data.get('trend')}

⚡ *Futures Signals (Binance {symbol})*
• Funding Rate: {futures['funding_rate']:+.4f}% (per 8h)
• Open Interest: {futures['open_interest']:,.0f} contracts
• Long/Short Ratio: {futures.get('long_short_ratio', 'N/A')}
• Signal: {futures_signal}

🔗 Sources: CoinGecko, Binance Futures public API
# Note: Nansen/Arkham require paid API keys - integrate similarly for smart money flows, entity labels, etc.
"""
    return msg.strip()

def send_telegram(message: str):
    """Send message to Telegram channel."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing Telegram credentials")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    resp = requests.post(url, json=payload, timeout=10)
    if resp.status_code == 200:
        print("Message sent successfully")
    else:
        print(f"Failed to send: {resp.text}")

def main():
    for coin in COINS:
        try:
            analysis = generate_analysis(coin)
            send_telegram(analysis)
            print(f"Processed {coin}")
        except Exception as e:
            print(f"Error on {coin}: {e}")
            send_telegram(f"⚠️ Error analyzing {coin}: {str(e)[:200]}")

if __name__ == "__main__":
    main()
