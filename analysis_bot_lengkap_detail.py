"""
Crypto Analysis Bot - VERSI LENGKAP + BANYAK COIN + FORMAT DETAIL
"""

import os
import sys
import time
import yaml
import requests
import pandas as pd
import ta
import mplfinance as mpf
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from io import BytesIO

# ===================== CONFIG =====================
def load_config():
    possible = ["config.yaml", "config/config.yaml"]
    for path in possible:
        if os.path.exists(path):
            print(f"✓ Config loaded: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    print("⚠️ Using default config")
    return {
        "coins": [
            "bitcoin", "ethereum", "binancecoin", "solana", "ripple",
            "cardano", "avalanche-2", "dogecoin", "chainlink", "the-open-network"
        ],
        "settings": {"send_charts": True, "include_ranking": True}
    }

CONFIG = load_config()
COINS = CONFIG.get("coins", ["bitcoin", "ethereum", "binancecoin", "solana", "ripple"])
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

def get_top_movers(order="price_change_percentage_24h_desc", limit=8):
    params = {
        "vs_currency": "usd",
        "order": order,
        "per_page": limit,
        "page": 1,
        "sparkline": False,
        "price_change_percentage": "24h"
    }
    data = request_retry(f"{CG_BASE}/coins/markets", params=params)
    return data or []

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
        "sentiment": data.get("sentiment_votes_up_percentage"),
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

def full_analysis(klines) -> Dict[str, Any]:
    if not klines or len(klines) < 60:
        return {"error": True}
    df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","i"])
    for col in ["o","h","l","c","v"]:
        df[col] = df[col].astype(float)

    df["rsi"] = ta.momentum.RSIIndicator(df["c"]).rsi()
    df["ema20"] = ta.trend.EMAIndicator(df["c"], 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["c"], 50).ema_indicator()
    atr = ta.volatility.AverageTrueRange(df["h"], df["l"], df["c"]).average_true_range()

    last = df.iloc[-1]
    price = last["c"]
    support = round(df["l"].tail(40).min(), 2)
    resistance = round(df["h"].tail(40).max(), 2)
    atr_val = last["atr"] if pd.notna(last["atr"]) else price * 0.02

    entry = round(price, 2)
    stop_loss = round(support * 0.995, 2)
    tp1 = round(price + atr_val * 1.5, 2)
    tp2 = round(price + atr_val * 2.5, 2)
    tp3 = round(price + atr_val * 4.0, 2)
    risk = entry - stop_loss
    rr1 = round((tp1 - entry) / risk, 2) if risk > 0 else 0

    trend = "Bullish" if price > last["ema20"] > last["ema50"] else \
             "Bearish" if price < last["ema20"] < last["ema50"] else "Neutral/Sideways"

    return {
        "price": round(price, 2),
        "rsi": round(last["rsi"], 1) if pd.notna(last["rsi"]) else None,
        "ema20": round(last["ema20"], 2),
        "ema50": round(last["ema50"], 2),
        "support": support,
        "resistance": resistance,
        "atr": round(atr_val, 2),
        "entry": entry,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "rr1": rr1,
        "trend": trend,
        "df": df,
    }

def create_candlestick_chart(symbol: str, klines) -> Optional[BytesIO]:
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
        print("❌ Secrets kosong")
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

def build_market_thesis(global_data):
    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    return f"""
📊 *ANALISA KRIPTO LENGKAP & DETAIL* — {now}

Gaya: Day Trade + Swing Trading
Data: CoinGecko + Binance Futures + Public APIs

*1) THESIS PASAR (MAKRO)*
• Total Market Cap: ±${(global_data.get('total_mcap') or 0)/1e12:.2f}T ({global_data.get('mcap_change') or 0:+.2f}% 24h)
• BTC Dominance: {global_data.get('btc_dom', 0):.1f}% | ETH Dominance: {global_data.get('eth_dom', 0):.1f}%
• Volume 24h: ${(global_data.get('total_vol') or 0)/1e9:.1f}B
• Kondisi: Large-cap relatif lebih stabil. Altcoin kecil berisiko tinggi.
• Strategi Utama: Buy-on-dip di support kuat + konfirmasi volume. Hindari FOMO.

_Analisa edukasi, bukan ajakan beli/jual. DYOR. Risiko kehilangan modal tinggi._
"""

def build_ranking(gainers, losers, high_vol):
    def fmt(items, title):
        lines = [f"*{title}*"]
        for i, c in enumerate(items[:7], 1):
            chg = c.get("price_change_percentage_24h") or 0
            vol = (c.get("total_volume") or 0) / 1e6
            lines.append(f"{i}. {c['symbol'].upper()} ${c['current_price']:,.4f} ({chg:+.2f}%) | Vol ${vol:.1f}M")
        return "\n".join(lines)
    return f"""
🏆 *RANKING 24 JAM*

{fmt(gainers, "🚀 Top Gainers")}

{fmt(losers, "🔻 Top Losers")}

{fmt(high_vol, "📈 Highest Volume")}
"""

def build_coin_detail(cg, analysis, futures):
    symbol = cg.get("symbol", "")
    price = cg.get("price", 0)
    from_ath = ((price / (cg.get("ath") or price)) - 1) * 100 if cg.get("ath") else 0
    rsi = analysis.get("rsi")
    trend = analysis.get("trend", "Neutral")

    thesis = "Bullish bias" if rsi and rsi < 55 and "Bull" in trend else \
             "Bearish / Cautious" if rsi and rsi > 65 else "Neutral / Range-bound"

    return f"""
*{symbol}/USDT* — Harga ±${price:,.2f}

*Thesis:* {thesis}
Trend 1H: {trend}

*Fundamental:*
• Perubahan: 24h {cg.get('chg24') or 0:+.2f}% | 7d {cg.get('chg7d') or 0:+.2f}% | 30d {cg.get('chg30d') or 0:+.2f}%
• Market Cap: ${(cg.get('mcap') or 0)/1e9:.1f}B
• Volume 24h: ${(cg.get('vol') or 0)/1e9:.1f}B
• Jarak dari ATH: {from_ath:+.1f}%
• Sentiment: {cg.get('sentiment') or 'N/A'}% Bullish

*Teknikal (1H):*
• RSI(14): {rsi}
• EMA20: ${analysis.get('ema20')} | EMA50: ${analysis.get('ema50')}
• Support: ${analysis.get('support')}
• Resistance: ${analysis.get('resistance')}
• ATR: ${analysis.get('atr')}

*Plan SWING (Spot):*
• Entry: ${analysis.get('entry')}
• Stop Loss: ${analysis.get('stop_loss')}
• TP1: ${analysis.get('tp1')} (R:R {analysis.get('rr1')})
• TP2: ${analysis.get('tp2')}
• TP3: ${analysis.get('tp3')}
• Invalidation: Close di bawah SL = batal long

⚡ *Sinyal Futures:*
• Funding Rate: {futures.get('funding', 0):+.4f}%
• Open Interest: {futures.get('oi', 0):,.0f}
• Long/Short Ratio: {futures.get('ls', 'N/A')}
• Catatan: Long hanya di support dengan SL ketat. Hindari leverage tinggi.

*Risk Management:*
• Risiko per trade maksimal 1%
• Ambil sebagian profit di TP1, geser SL ke entry
• Maks 1–2 posisi terbuka bersamaan
"""

def build_additional():
    return """
📊 *DATA TAMBAHAN & DAY TRADING PLAN*

*On-chain (Dummy — Nansen/Arkham Style)*
• Smart Money: Net accumulation di beberapa large-cap
• Whale activity: Mixed (sebagian distribusi, sebagian akumulasi)
• Perp positioning: Mild long bias di BTC & BNB

*Day Trading Plan (Sesi Aktif)*
• Fokus range trading di large-cap (BTC, ETH, BNB)
• Long: Beli di support setelah konfirmasi volume
• Short: Jual di resistance dengan SL ketat
• Hindari breakout tanpa volume
• Kurangi aktivitas sebelum event makro besar

⚠️ *HINDARI*
• Altcoin kecil & meme coin (rawan pump-dump)
• Overtrade saat volatilitas tinggi
• Leverage tinggi tanpa manajemen risiko
"""

def main():
    print("=== VERSI LENGKAP + BANYAK COIN ===")
    global_data = get_global()

    send_text(build_market_thesis(global_data).strip())
    time.sleep(2)

    if SETTINGS.get("include_ranking", True):
        gainers = get_top_movers("price_change_percentage_24h_desc")
        losers = get_top_movers("price_change_percentage_24h_asc")
        high_vol = get_top_movers("volume_desc")
        send_text(build_ranking(gainers, losers, high_vol).strip())
        time.sleep(2)

    for coin_id in COINS:
        print(f"Analyzing {coin_id}")
        cg = get_coin(coin_id)
        if not cg.get("symbol"):
            continue
        symbol = f"{cg['symbol']}USDT"
        klines = get_klines(symbol, "1h", 100)
        analysis = full_analysis(klines)
        futures = get_futures(symbol)
        report = build_coin_detail(cg, analysis, futures)
        send_text(report.strip())

        if SETTINGS.get("send_charts", True) and not analysis.get("error"):
            chart = create_candlestick_chart(symbol, klines)
            if chart:
                send_photo(chart, f"📈 {symbol} 1H Chart + EMA")
                chart.close()
        time.sleep(3)

    send_text(build_additional().strip())
    time.sleep(1)

    send_text("""
⚠️ *DISCLAIMER*
Analisa ini bersifat edukasi, bukan ajakan beli/jual.
Kripto berisiko tinggi dan sangat volatil.
Gunakan manajemen risiko yang ketat dan dana yang siap hilang.
Keputusan dan risiko sepenuhnya ada di Anda.

_Data: CoinGecko, Binance Futures, Public APIs_
""")
    print("=== SELESAI ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
