"""
Crypto Analysis Bot - Format Channel Style
Mirip dengan postingan manual di channel Mitecho Kripto
"""

import os
import sys
import time
import yaml
import requests
import pandas as pd
import ta
from datetime import datetime, timezone
from typing import Dict, Any

# ===================== CONFIG =====================
def load_config():
    possible = ["config.yaml", "config/config.yaml"]
    for path in possible:
        if os.path.exists(path):
            print(f"✓ Config loaded: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    print("⚠️ Using default config")
    return {"coins": ["bitcoin", "ethereum", "binancecoin", "solana", "ripple"]}

CONFIG = load_config()
COINS = CONFIG.get("coins", ["bitcoin", "ethereum", "binancecoin"])
SETTINGS = CONFIG.get("settings", {})

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

def get_global():
    data = request_retry(f"{CG_BASE}/global")
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

def get_coin(coin_id: str):
    params = {"localization": "false", "tickers": "false", "market_data": "true"}
    data = request_retry(f"{CG_BASE}/coins/{coin_id}", params=params)
    if not data:
        return {}
    m = data.get("market_data", {})
    return {
        "name": data.get("name"),
        "symbol": data.get("symbol", "").upper(),
        "price": m.get("current_price", {}).get("usd"),
        "chg24": m.get("price_change_percentage_24h"),
        "chg7d": m.get("price_change_percentage_7d"),
        "chg30d": m.get("price_change_percentage_30d"),
        "mcap": m.get("market_cap", {}).get("usd"),
        "vol": m.get("total_volume", {}).get("usd"),
        "ath": m.get("ath", {}).get("usd"),
    }

def get_klines(symbol: str, interval: str = "1h", limit: int = 100):
    data = request_retry(f"{BINANCE}/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    return data or []

def get_futures(symbol: str):
    res = {}
    prem = request_retry(f"{BINANCE}/fapi/v1/premiumIndex", {"symbol": symbol})
    if prem:
        res["funding"] = float(prem.get("lastFundingRate", 0)) * 100
    oi = request_retry(f"{BINANCE}/fapi/v1/openInterest", {"symbol": symbol})
    if oi:
        res["oi"] = float(oi.get("openInterest", 0))
    ls = request_retry(f"{BINANCE}/futures/data/globalLongShortAccountRatio",
                       {"symbol": symbol, "period": "5m", "limit": 1})
    if ls and isinstance(ls, list) and ls:
        res["ls"] = float(ls[0].get("longShortRatio", 0))
    return res

def analyze_simple(klines):
    if not klines or len(klines) < 50:
        return {}
    df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","i"])
    for col in ["o","h","l","c","v"]:
        df[col] = df[col].astype(float)
    df["rsi"] = ta.momentum.RSIIndicator(df["c"]).rsi()
    df["ema20"] = ta.trend.EMAIndicator(df["c"], 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["c"], 50).ema_indicator()
    last = df.iloc[-1]
    support = round(df["l"].tail(30).min(), 2)
    resistance = round(df["h"].tail(30).max(), 2)
    return {
        "rsi": round(last["rsi"], 1) if pd.notna(last["rsi"]) else None,
        "ema20": round(last["ema20"], 2),
        "ema50": round(last["ema50"], 2),
        "support": support,
        "resistance": resistance,
        "price": round(last["c"], 2),
    }

def send_text(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Secrets kosong")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4090],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }, timeout=15)
    print(f"Telegram: {r.status_code}")
    return r.status_code == 200

def build_market_thesis(global_data):
    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    btc_dom = global_data.get("btc_dom", 0)
    mcap = global_data.get("total_mcap", 0) / 1e12
    return f"""
📊 *ANALISA KRIPTO* — {now}

Gaya: Day trade + Swing | Spot & sinyal Futures
Data: CoinGecko + Binance Futures + Public APIs

*1) THESIS PASAR (MAKRO)*
• Total Market Cap: ±${mcap:.2f}T
• BTC Dominance: {btc_dom:.1f}% | ETH Dominance: {global_data.get('eth_dom', 0):.1f}%
• Market masih dalam fase wait-and-see. Fokus pada large-cap yang relatif kuat.
• Strategi: Buy-on-dip di support kuat, hindari overtrade sebelum event makro.

_Analisa edukasi, bukan ajakan beli/jual. DYOR._
"""

def build_coin_report(cg, ta_data, futures):
    symbol = cg.get("symbol", "")
    price = cg.get("price", 0)
    chg24 = cg.get("chg24") or 0
    chg7d = cg.get("chg7d") or 0
    support = ta_data.get("support", "N/A")
    resistance = ta_data.get("resistance", "N/A")
    rsi = ta_data.get("rsi", "N/A")
    funding = futures.get("funding", 0)

    # Simple thesis
    if chg24 > 1 and rsi and rsi < 60:
        thesis = "Menguji resistance. Cocok swing dengan konfirmasi."
    elif chg24 < -2:
        thesis = "Melemah. Hanya rebound cepat atau tunggu support."
    else:
        thesis = "Sideways. Cocok range trading."

    # Simple plan
    entry_low = round(price * 0.985, 2)
    entry_high = round(price * 0.995, 2)
    sl = round(support * 0.99, 2) if isinstance(support, (int, float)) else round(price * 0.97, 2)
    tp1 = round(price * 1.015, 2)
    tp2 = round(price * 1.03, 2)
    tp3 = round(price * 1.05, 2)

    return f"""
*{symbol}/USDT* — Harga ±${price:,.2f}

*Thesis:* {thesis}

*Fundamental:*
• 24h: {chg24:+.2f}% | 7d: {chg7d:+.2f}%
• Market Cap: ${(cg.get('mcap') or 0)/1e9:.1f}B
• Volume 24h: ${(cg.get('vol') or 0)/1e9:.1f}B

*Teknikal (1H):*
• RSI: {rsi}
• EMA20: ${ta_data.get('ema20', 'N/A')} | EMA50: ${ta_data.get('ema50', 'N/A')}
• Support: {support} | Resistance: {resistance}

*Plan SWING:*
• Entry: {entry_low}–{entry_high}
• SL: {sl}
• TP1: {tp1} | TP2: {tp2} | TP3: {tp3}

⚡ *Futures:*
• Funding: {funding:+.4f}%
• OI: {futures.get('oi', 0):,.0f}
• L/S: {futures.get('ls', 'N/A')}
• Bias: {'Long' if funding > 0 else 'Short'} hanya di support dengan SL ketat.
"""

def build_onchain_dummy():
    return """
📊 *DATA TAMBAHAN — On-chain & Flow*

*CoinMarketCap / CoinGecko*
• Market masih didominasi large-cap.
• Altcoin kecil berisiko tinggi (pump-dump).

*Arkham / Nansen (Dummy)*
• Whale activity terdeteksi di beberapa large-cap.
• Smart money cenderung akumulasi di support.
• Perp positioning: Mixed.

*ETF Flow (Dummy)*
• BTC ETF: Mixed flow.
• ETH ETF: Masih lemah.

_Kesimpulan: Fokus large-cap, hindari overtrade._
"""

def main():
    print("=== Channel Style Analysis ===")
    global_data = get_global()

    # 1. Market Thesis
    thesis_msg = build_market_thesis(global_data)
    send_text(thesis_msg.strip())
    time.sleep(2)

    # 2. Per Coin
    for coin_id in COINS:
        print(f"Processing {coin_id}")
        cg = get_coin(coin_id)
        if not cg.get("symbol"):
            continue
        symbol = f"{cg['symbol']}USDT"
        klines = get_klines(symbol, "1h", 80)
        ta_data = analyze_simple(klines)
        futures = get_futures(symbol)
        report = build_coin_report(cg, ta_data, futures)
        send_text(report.strip())
        time.sleep(2)

    # 3. On-chain Dummy
    onchain = build_onchain_dummy()
    send_text(onchain.strip())

    # 4. Disclaimer
    disclaimer = """
⚠️ *Analisa edukasi, bukan ajakan beli/jual.*
Kripto berisiko tinggi. Gunakan manajemen risiko & dana yang siap hilang.
Keputusan & risiko ada di Anda.

_Data: CoinGecko, Binance Futures, Public APIs_
"""
    send_text(disclaimer.strip())
    print("=== Done ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
