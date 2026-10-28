"""
Crypto Analysis Bot ADVANCED+++ 
Deep Analysis + Detailed Risk/Reward + Volume Profile Chart
"""

import os
import sys
import time
import yaml
import requests
import pandas as pd
import ta
import mplfinance as mpf
import matplotlib.pyplot as plt
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
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

def get_top_movers(order="price_change_percentage_24h_desc", limit=10):
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
        "chg30d": m.get("price_change_percentage_30d"),
        "ath": m.get("ath", {}).get("usd"),
        "circ": m.get("circulating_supply"),
        "sentiment": data.get("sentiment_votes_up_percentage"),
    }

def get_klines(symbol: str, interval: str, limit: int = 120):
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
        res["long_account"] = float(ls[0].get("longAccount", 0))
        res["short_account"] = float(ls[0].get("shortAccount", 0))
    return res

def get_nansen_deep(symbol: str) -> str:
    if not NANSEN_CFG.get("enabled", False):
        return ""
    if NANSEN_CFG.get("use_real_api") and NANSEN_API_KEY:
        return "🔗 *Nansen Smart Money* (Real API aktif)"
    return (
        f"🧠 *Nansen Smart Money (Dummy)*\n"
        f"• 24h Netflow: +$18.7M (net accumulation)\n"
        f"• Active Smart Money wallets: 14\n"
        f"• Large transfers: 6 in / 2 out\n"
        f"• Perp bias: Mild long\n"
        f"_Isi NANSEN_API_KEY + set use_real_api: true untuk data asli_"
    )

def deep_technical_analysis(klines) -> Dict[str, Any]:
    if not klines or len(klines) < 60:
        return {"error": True}
    df = pd.DataFrame(klines, columns=["t","o","h","l","c","v","ct","qv","n","tb","tq","i"])
    for col in ["o","h","l","c","v"]:
        df[col] = df[col].astype(float)

    df["rsi"] = ta.momentum.RSIIndicator(df["c"], window=14).rsi()
    macd = ta.trend.MACD(df["c"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["ema20"] = ta.trend.EMAIndicator(df["c"], 20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(df["c"], 50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(df["c"], 200).ema_indicator()
    bb = ta.volatility.BollingerBands(df["c"], window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    atr = ta.volatility.AverageTrueRange(df["h"], df["l"], df["c"], window=14)
    df["atr"] = atr.average_true_range()

    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last["c"]

    recent_high = df["h"].tail(50).max()
    recent_low = df["l"].tail(50).min()
    atr_val = last["atr"] if pd.notna(last["atr"]) else price * 0.02

    # Detailed Risk/Reward
    entry = round(price, 2)
    stop_loss = round(recent_low - atr_val * 0.5, 2)
    target1 = round(price + atr_val * 1.5, 2)
    target2 = round(price + atr_val * 3.0, 2)
    risk = entry - stop_loss
    reward1 = target1 - entry
    reward2 = target2 - entry
    rr1 = round(reward1 / risk, 2) if risk > 0 else 0
    rr2 = round(reward2 / risk, 2) if risk > 0 else 0

    # Volume Profile sederhana
    price_bins = pd.cut(df["c"], bins=12)
    vol_profile = df.groupby(price_bins, observed=False)["v"].sum()
    poc_bin = vol_profile.idxmax()
    poc_low = round(poc_bin.left, 2) if hasattr(poc_bin, "left") else round(price * 0.98, 2)
    poc_high = round(poc_bin.right, 2) if hasattr(poc_bin, "right") else round(price * 1.02, 2)

    trend = "Strong Bullish" if price > last["ema20"] > last["ema50"] > last["ema200"] else \
             "Bullish" if price > last["ema20"] > last["ema50"] else \
             "Bearish" if price < last["ema20"] < last["ema50"] else \
             "Strong Bearish" if price < last["ema20"] < last["ema50"] < last["ema200"] else "Neutral/Sideways"

    macd_cross = "Bullish Cross" if (prev["macd"] < prev["macd_signal"] and last["macd"] > last["macd_signal"]) else \
                 "Bearish Cross" if (prev["macd"] > prev["macd_signal"] and last["macd"] < last["macd_signal"]) else "No recent cross"

    return {
        "price": round(price, 2),
        "rsi": round(last["rsi"], 1) if pd.notna(last["rsi"]) else None,
        "rsi_status": "Oversold" if last["rsi"] < 30 else "Overbought" if last["rsi"] > 70 else "Neutral",
        "macd_cross": macd_cross,
        "ema20": round(last["ema20"], 2),
        "ema50": round(last["ema50"], 2),
        "ema200": round(last["ema200"], 2) if pd.notna(last["ema200"]) else None,
        "bb_upper": round(last["bb_upper"], 2),
        "bb_lower": round(last["bb_lower"], 2),
        "trend": trend,
        "support": round(recent_low, 2),
        "resistance": round(recent_high, 2),
        "atr": round(atr_val, 2),
        "entry": entry,
        "stop_loss": stop_loss,
        "target1": target1,
        "target2": target2,
        "rr1": rr1,
        "rr2": rr2,
        "poc_low": poc_low,
        "poc_high": poc_high,
        "df": df,  # untuk chart volume profile
    }

def multi_timeframe_deep(symbol: str) -> Dict:
    intervals = {"15m": "15m", "1h": "1h", "4h": "4h", "1d": "1d"}
    result = {}
    for name, iv in intervals.items():
        klines = get_klines(symbol, iv, 100)
        ta_data = deep_technical_analysis(klines)
        ta_data["tf"] = name
        result[name] = ta_data
    return result

def generate_deep_thesis(cg, futures, mtf) -> str:
    change24 = cg.get("chg24") or 0
    funding = futures.get("funding") or 0
    ls = futures.get("ls") or 1
    trend_1h = mtf.get("1h", {}).get("trend", "Neutral")
    trend_4h = mtf.get("4h", {}).get("trend", "Neutral")
    trend_1d = mtf.get("1d", {}).get("trend", "Neutral")

    confluence = sum([
        1 if "Bull" in str(trend_1h) else 0,
        1 if "Bull" in str(trend_4h) else 0,
        1 if "Bull" in str(trend_1d) else 0,
    ])

    if confluence >= 2 and funding < 0.015 and ls < 2.0:
        bias = "Bullish Bias (Multi-TF confluence)"
        detail = "Trend higher timeframes mendukung. Cocok swing long dengan konfirmasi entry di timeframe lebih rendah."
    elif confluence <= 1 and funding > 0.01 and ls > 1.7:
        bias = "Cautious / Bearish Bias"
        detail = "Long crowding + funding tinggi. Risiko flush meningkat. Lebih baik tunggu pullback atau short pada resistance."
    elif change24 < -4 and funding < 0:
        bias = "Potential Bounce"
        detail = "Funding negatif + harga turun. Pantau short squeeze atau akumulasi di support."
    else:
        bias = "Neutral / Range-bound"
        detail = "Tidak ada konfluensi kuat. Cocok day trading range. Hindari breakout tanpa volume."

    return f"*{bias}*\n{detail}"

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
                 savefig=dict(fname=buf, dpi=110, bbox_inches="tight"))
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"Chart error: {e}")
        return None

def create_volume_profile_chart(symbol: str, df: pd.DataFrame) -> Optional[BytesIO]:
    """Chart Volume Profile sederhana."""
    try:
        if df is None or len(df) < 30:
            return None
        price_bins = pd.cut(df["c"], bins=15)
        vol_profile = df.groupby(price_bins, observed=False)["v"].sum().sort_index()

        fig, ax = plt.subplots(figsize=(8, 6))
        y_pos = range(len(vol_profile))
        ax.barh(y_pos, vol_profile.values, color="steelblue", alpha=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels([f"{int(b.left)}-{int(b.right)}" for b in vol_profile.index], fontsize=8)
        ax.set_xlabel("Volume")
        ax.set_title(f"{symbol} Volume Profile (1H)")
        ax.invert_yaxis()
        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"Volume Profile chart error: {e}")
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

def build_deep_message(cg, futures, mtf, nansen_txt):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    price = cg.get("price") or 0
    ath = cg.get("ath") or 0
    from_ath = ((price / ath) - 1) * 100 if ath else 0
    thesis = generate_deep_thesis(cg, futures, mtf)

    tf1h = mtf.get("1h", {})
    support = tf1h.get("support", "N/A")
    resistance = tf1h.get("resistance", "N/A")
    entry = tf1h.get("entry", "N/A")
    stop_loss = tf1h.get("stop_loss", "N/A")
    target1 = tf1h.get("target1", "N/A")
    target2 = tf1h.get("target2", "N/A")
    rr1 = tf1h.get("rr1", "N/A")
    rr2 = tf1h.get("rr2", "N/A")
    poc_low = tf1h.get("poc_low", "N/A")
    poc_high = tf1h.get("poc_high", "N/A")

    mtf_lines = []
    for tf_name in ["15m", "1h", "4h", "1d"]:
        d = mtf.get(tf_name, {})
        if d.get("error"):
            continue
        mtf_lines.append(
            f"• *{tf_name}*: {d.get('trend')} | RSI {d.get('rsi')} ({d.get('rsi_status')}) | "
            f"EMA20 ${d.get('ema20')}"
        )

    funding = futures.get("funding", 0)
    funding_note = "Longs bayar shorts" if funding > 0 else "Shorts bayar longs"

    msg = f"""
📊 *{cg.get('name')} ({cg.get('symbol')})* | {now}
*Deep Analysis + Risk/Reward*

🎯 *THESIS*
{thesis}

📈 *FUNDAMENTAL*
• Price: ${price:,.2f}
• 24h: {cg.get('chg24') or 0:+.2f}% | 7d: {cg.get('chg7d') or 0:+.2f}% | 30d: {cg.get('chg30d') or 0:+.2f}%
• Market Cap: ${(cg.get('mcap') or 0)/1e9:.2f}B
• Volume 24h: ${(cg.get('vol') or 0)/1e9:.2f}B
• From ATH: {from_ath:+.1f}%
• Sentiment: {cg.get('sentiment') or 'N/A'}% Bullish

📊 *MULTI-TIMEFRAME*
{chr(10).join(mtf_lines) or 'Data tidak cukup'}

🎯 *RISK / REWARD (1H)*
• Entry: ${entry}
• Stop Loss: ${stop_loss}
• Target 1: ${target1} (R:R {rr1})
• Target 2: ${target2} (R:R {rr2})
• Support: ${support} | Resistance: ${resistance}
• Volume Profile (POC): ${poc_low} – ${poc_high}
• EMA20: ${tf1h.get('ema20', 'N/A')} | EMA50: ${tf1h.get('ema50', 'N/A')}
• ATR: ${tf1h.get('atr', 'N/A')}

⚡ *FUTURES*
• Funding: {funding:+.4f}% → {funding_note}
• Open Interest: {futures.get('oi', 0):,.0f}
• L/S Ratio: {futures.get('ls', 'N/A')}
• Long Accounts: {futures.get('long_account', 'N/A')}% | Short: {futures.get('short_account', 'N/A')}%

{nansen_txt}

⚠️ *Risk Note*
R:R bersifat probabilistik. Selalu gunakan stop loss dan manajemen posisi. DYOR.
#Crypto #DeepAnalysis #{cg.get('symbol')}
"""
    return msg.strip()

def build_detailed_ranking(gainers, losers, high_vol):
    def fmt(items, title):
        lines = [f"*{title}*"]
        for i, c in enumerate(items[:8], 1):
            chg = c.get("price_change_percentage_24h") or 0
            vol = c.get("total_volume") or 0
            lines.append(f"{i}. {c['symbol'].upper()} ${c['current_price']:,.4f} ({chg:+.2f}%) | Vol ${vol/1e6:.1f}M")
        return "\n".join(lines)

    msg = f"""
🏆 *DETAILED RANKING 24H*

{fmt(gainers, "🚀 Top Gainers")}

{fmt(losers, "🔻 Top Losers")}

{fmt(high_vol, "📈 Highest Volume")}
"""
    return msg.strip()

def main():
    print("=== DEEP+++ Crypto Analysis Bot ===")
    global_data = get_global()

    if SETTINGS.get("include_global_summary", True) and global_data:
        gmsg = f"""
🌐 *GLOBAL CRYPTO MARKET*
{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
• Total Market Cap: ${(global_data.get('total_mcap') or 0)/1e12:.2f}T ({global_data.get('mcap_change') or 0:+.2f}% 24h)
• Volume 24h: ${(global_data.get('total_vol') or 0)/1e9:.1f}B
• BTC Dominance: {global_data.get('btc_dom', 0):.2f}%
• ETH Dominance: {global_data.get('eth_dom', 0):.2f}%
"""
        send_text(gmsg.strip())
        time.sleep(1)

    if SETTINGS.get("include_top_gainers", True):
        gainers = get_top_movers("price_change_percentage_24h_desc")
        losers = get_top_movers("price_change_percentage_24h_asc")
        high_vol = get_top_movers("volume_desc")
        if gainers or losers:
            send_text(build_detailed_ranking(gainers, losers, high_vol))
            time.sleep(1)

    for coin_id in COINS:
        print(f"\n--- Analyzing {coin_id} ---")
        try:
            cg = get_coin(coin_id)
            if not cg.get("symbol"):
                continue
            symbol = f"{cg['symbol']}USDT"
            futures = get_futures(symbol)
            mtf = multi_timeframe_deep(symbol) if SETTINGS.get("multi_timeframe", True) else {}
            nansen = get_nansen_deep(cg["symbol"])
            msg = build_deep_message(cg, futures, mtf, nansen)
            send_text(msg)

            if SETTINGS.get("send_charts", True):
                # Candlestick chart
                klines = get_klines(symbol, "1h", 100)
                chart = create_candlestick_chart(symbol, klines)
                if chart:
                    send_photo(chart, f"📈 {cg['symbol']} 1H Candlestick + EMA")
                    chart.close()

                # Volume Profile chart
                tf1h = mtf.get("1h", {})
                if "df" in tf1h:
                    vp_chart = create_volume_profile_chart(symbol, tf1h["df"])
                    if vp_chart:
                        send_photo(vp_chart, f"📊 {cg['symbol']} Volume Profile (1H)")
                        vp_chart.close()

            time.sleep(3)
        except Exception as e:
            print(f"Error on {coin_id}: {e}")
            send_text(f"⚠️ Error analisis *{coin_id}*: {str(e)[:250]}")

    print("=== Analysis Complete ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
