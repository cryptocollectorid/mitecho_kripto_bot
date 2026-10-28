"""
Crypto Analysis Bot ADVANCED
Disesuaikan dengan struktur file di ROOT repository
"""

import os
import sys
import time
import yaml
import requests
import pandas as pd
import ta
import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from io import BytesIO

# ===================== CONFIG =====================
def load_config():
    possible = [
        "config.yaml",                    # di root (sesuai repo kamu sekarang)
        "config/config.yaml",
        os.path.join(os.path.dirname(__file__), "config.yaml"),
        os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml"),
    ]
    for path in possible:
        if os.path.exists(path):
            print(f"✓ Config loaded from: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    print("⚠️ Config tidak ditemukan, menggunakan default")
    return {
        "coins": ["bitcoin", "ethereum", "solana"],
        "settings": {"send_charts": True, "include_top_gainers": True, "multi_timeframe": True},
        "signals": {"rsi_oversold": 30, "rsi_overbought": 70},
        "nansen": {"enabled": True, "use_real_api": False}
    }

CONFIG = load_config()
COINS = CONFIG.get("coins", ["bitcoin"])
SETTINGS = CONFIG.get("settings", {})
SIGNALS = CONFIG.get("signals", {})
NANSEN_CFG = CONFIG.get("nansen", {})

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
NANSEN_API_KEY = os.getenv("NANSEN_API_KEY")

CG_BASE = "https://api.coingecko.com/api/v3"
BINANCE = "https://fapi.binance.com"

def request_retry(url, params=None, headers=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(2 ** i)
                continue
        except Exception as e:
            print(f"Request error: {e}")
            time.sleep(1)
    return None

def get_headers():
    h = {}
    if COINGECKO_API_KEY:
        h["x-cg-demo-api-key"] = COINGECKO_API_KEY
    return h

def get_global():
    data = request_retry(f"{CG_BASE}/global", headers=get_headers())
    if not data or "data" not in data:
        return {}
    d = data["data"]
    return {
        "total_mcap": d.get("total_market_cap", {}).get("usd"),
        "total_vol": d.get("total_volume", {}).get("usd"),
        "btc_dom": d.get("market_cap_percentage", {}).get("btc"),
        "eth_dom": d.get("market_cap_percentage", {}).get("eth"),
        "mcap_change": d.get("market_cap_change_percentage_24h_usd"),
    }

def get_top_movers(order="price_change_percentage_24h_desc", limit=8):
    params = {
        "vs_currency": "usd",
        "order": order,
        "per_page": limit,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h"
    }
    data = request_retry(f"{CG_BASE}/coins/markets", params=params, headers=get_headers())
    return data or []

def get_coin(coin_id: str):
    params = {"localization": "false", "tickers": "false", "market_data": "true", "community_data": "true"}
    data = request_retry(f"{CG_BASE}/coins/{coin_id}", params=params, headers=get_headers())
    if not data:
        return {}
    m = data.get("market_data", {})
    return {
        "name": data.get("name"),
        "symbol": data.get("symbol", "").upper(),
        "price": m.get("current_price", {}).get("usd"),
        "mcap": m.get("market_cap", {}).get("usd"),
        "vol": m.get("total_volume", {}).get("usd"),
        "chg24": m.get("price_change_percentage_24h"),
        "chg7d": m.get("price_change_percentage_7d"),
        "ath": m.get("ath", {}).get("usd"),
        "circ": m.get("circulating_supply"),
        "sentiment": data.get("sentiment_votes_up_percentage"),
    }

def get_klines(symbol: str, interval: str, limit: int = 100):
    data = request_retry(f"{BINANCE}/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    return data or []

def get_futures(symbol: str):
    res = {}
    prem = request_retry(f"{BINANCE}/fapi/v1/premiumIndex", {"symbol": symbol})
    if prem:
        res["funding"] = float(prem.get("lastFundingRate", 0)) * 100
        res["mark"] = float(prem.get("markPrice", 0))
    oi = request_retry(f"{BINANCE}/fapi/v1/openInterest", {"symbol": symbol})
    if oi:
        res["oi"] = float(oi.get("openInterest", 0))
    ls = request_retry(f"{BINANCE}/futures/data/globalLongShortAccountRatio",
                       {"symbol": symbol, "period": "5m", "limit": 1})
    if ls and isinstance(ls, list) and ls:
        res["ls"] = float(ls[0].get("longShortRatio", 0))
    return res

def get_nansen_dummy(symbol: str) -> str:
    if not NANSEN_CFG.get("enabled", False):
        return ""
    if NANSEN_CFG.get("use_real_api") and NANSEN_API_KEY:
        return "🔗 Nansen: (Real API placeholder)"
    return (
        f"🧠 *Nansen Smart Money (Dummy)*\n"
        f"• Netflow 24h: +$12.4M (accumulation)\n"
        f"• Top wallets buying: 3 whale wallets\n"
        f"• Perp positioning: Mild long bias\n"
        f"_Set use_real_api: true + NANSEN_API_KEY untuk data asli_"
    )

def analyze_tf(klines, tf_name: str) -> Dict:
    if not klines or len(klines) < 30:
        return {"tf": tf_name, "error": True}
    df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","i"])
    for col in ["o","h","l","c","v"]:
        df[col] = df[col].astype(float)
    df["rsi"] = ta.momentum.RSIIndicator(df["c"]).rsi()
    df["ema20"] = ta.trend.EMAIndicator(df["c"], 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["c"], 50).ema_indicator()
    last = df.iloc[-1]
    trend = "Bull" if last["c"] > last["ema20"] > last["ema50"] else "Bear" if last["c"] < last["ema20"] < last["ema50"] else "Neutral"
    return {
        "tf": tf_name,
        "price": round(last["c"], 2),
        "rsi": round(last["rsi"], 1) if pd.notna(last["rsi"]) else None,
        "trend": trend,
        "ema20": round(last["ema20"], 2),
        "ema50": round(last["ema50"], 2),
    }

def multi_timeframe_analysis(symbol: str) -> Dict:
    intervals = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    result = {}
    for name, iv in intervals.items():
        klines = get_klines(symbol, iv, 80)
        result[name] = analyze_tf(klines, name)
    return result

def create_chart(symbol: str, klines) -> Optional[BytesIO]:
    if not klines or len(klines) < 50:
        return None
    try:
        df = pd.DataFrame(klines, columns=["Date","Open","High","Low","Close","Volume","ct","qv","n","tb","tq","i"])
        df["Date"] = pd.to_datetime(df["Date"], unit="ms")
        df.set_index("Date", inplace=True)
        for c in ["Open","High","Low","Close","Volume"]:
            df[c] = df[c].astype(float)
        df["EMA20"] = df["Close"].ewm(span=20).mean()
        df["EMA50"] = df["Close"].ewm(span=50).mean()
        apds = [
            mpf.make_addplot(df["EMA20"], color="orange", width=1),
            mpf.make_addplot(df["EMA50"], color="blue", width=1),
        ]
        buf = BytesIO()
        mpf.plot(df, type="candle", style="charles", addplot=apds,
                 volume=True, title=f"{symbol} 1H", ylabel="Price",
                 savefig=dict(fname=buf, dpi=100, bbox_inches="tight"))
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"Chart error: {e}")
        return None

def send_text(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram secrets missing")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4090],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }, timeout=15)
    return r.status_code == 200

def send_photo(buf: BytesIO, caption: str = ""):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {"photo": ("chart.png", buf, "image/png")}
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024], "parse_mode": "Markdown"}
    r = requests.post(url, files=files, data=data, timeout=30)
    return r.status_code == 200

def build_top_movers_msg(gainers, losers):
    def fmt(items, title):
        lines = [f"*{title}*"]
        for i, c in enumerate(items[:SETTINGS.get("top_movers_count", 8)], 1):
            chg = c.get("price_change_percentage_24h") or 0
            lines.append(f"{i}. {c['symbol'].upper()} ${c['current_price']:,.4f} ({chg:+.2f}%)")
        return "\n".join(lines)
    return f"{fmt(gainers, '🚀 Top Gainers 24h')}\n\n{fmt(losers, '🔻 Top Losers 24h')}"

def build_coin_message(cg, futures, mtf, nansen_txt):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    price = cg.get("price") or 0
    ath = cg.get("ath") or 0
    from_ath = ((price / ath) - 1) * 100 if ath else 0
    mtf_lines = []
    for tf, d in mtf.items():
        if d.get("error"):
            continue
        mtf_lines.append(f"• {tf}: {d['trend']} | RSI {d.get('rsi')} | EMA20 ${d.get('ema20')}")
    msg = f"""
📊 *{cg.get('name')} ({cg.get('symbol')})* | {now}

🎯 *THESIS*
Neutral-to-Cautious. Multi-timeframe + futures confirmation.
_Day + Swing | DYOR_

📈 *FUNDAMENTAL*
• Price: ${price:,.2f} ({cg.get('chg24') or 0:+.2f}% 24h | {cg.get('chg7d') or 0:+.2f}% 7d)
• MCap: ${(cg.get('mcap') or 0)/1e9:.2f}B | Vol: ${(cg.get('vol') or 0)/1e9:.2f}B
• From ATH: {from_ath:+.1f}%
• Sentiment: {cg.get('sentiment') or 'N/A'}% Bullish

📊 *MULTI-TIMEFRAME*
{chr(10).join(mtf_lines) or 'No data'}

⚡ *FUTURES (Binance)*
• Funding: {futures.get('funding', 0):+.4f}%
• OI: {futures.get('oi', 0):,.0f}
• L/S Ratio: {futures.get('ls', 'N/A')}

{nansen_txt}
"""
    return msg.strip()

def main():
    print("=== ADVANCED Crypto Analysis Bot ===")
    global_data = get_global()

    if SETTINGS.get("include_global_summary", True) and global_data:
        gmsg = f"""
🌐 *GLOBAL MARKET*
{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
• Total MCap: ${(global_data.get('total_mcap') or 0)/1e12:.2f}T ({global_data.get('mcap_change') or 0:+.2f}%)
• Volume 24h: ${(global_data.get('total_vol') or 0)/1e9:.1f}B
• BTC Dom: {global_data.get('btc_dom', 0):.2f}% | ETH Dom: {global_data.get('eth_dom', 0):.2f}%
"""
        send_text(gmsg.strip())
        time.sleep(1)

    if SETTINGS.get("include_top_gainers", True):
        gainers = get_top_movers("price_change_percentage_24h_desc")
        losers = get_top_movers("price_change_percentage_24h_asc")
        if gainers or losers:
            send_text(build_top_movers_msg(gainers, losers))
            time.sleep(1)

    for coin_id in COINS:
        print(f"\n--- {coin_id} ---")
        try:
            cg = get_coin(coin_id)
            if not cg.get("symbol"):
                continue
            symbol = f"{cg['symbol']}USDT"
            futures = get_futures(symbol)
            mtf = multi_timeframe_analysis(symbol) if SETTINGS.get("multi_timeframe") else {}
            nansen = get_nansen_dummy(cg["symbol"])
            msg = build_coin_message(cg, futures, mtf, nansen)
            send_text(msg)

            if SETTINGS.get("send_charts", True):
                klines = get_klines(symbol, "1h", 100)
                chart = create_chart(symbol, klines)
                if chart:
                    send_photo(chart, f"📈 {cg['symbol']} 1H Chart (EMA20/50)")
                    chart.close()
            time.sleep(3)
        except Exception as e:
            print(f"Error {coin_id}: {e}")
            send_text(f"⚠️ Error {coin_id}: {str(e)[:200]}")

    print("=== Done ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
