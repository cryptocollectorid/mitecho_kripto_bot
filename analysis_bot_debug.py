"""
Crypto Analysis Bot - Debug Version
Menampilkan error Telegram dengan lebih jelas
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
    return {"coins": ["bitcoin", "ethereum"], "settings": {"include_global_summary": True}}

CONFIG = load_config()
COINS = CONFIG.get("coins", ["bitcoin"])
SETTINGS = CONFIG.get("settings", {})

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print(f"DEBUG - Token exists: {bool(TELEGRAM_BOT_TOKEN)}")
print(f"DEBUG - Chat ID: {TELEGRAM_CHAT_ID}")

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
        "mcap": m.get("market_cap", {}).get("usd"),
    }

def send_text(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ TELEGRAM_BOT_TOKEN atau TELEGRAM_CHAT_ID kosong!")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text[:4090],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"Telegram response: {r.status_code} - {r.text[:300]}")
        if r.status_code == 200:
            print("✓ Pesan terkirim")
            return True
        else:
            print(f"✗ Gagal kirim: {r.status_code}")
            return False
    except Exception as e:
        print(f"✗ Exception kirim Telegram: {e}")
        return False

def main():
    print("=== DEBUG MODE ===")
    global_data = get_global()

    if global_data:
        gmsg = f"""
🌐 *GLOBAL CRYPTO MARKET*
{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
• Total Market Cap: ${(global_data.get('total_mcap') or 0)/1e12:.2f}T ({global_data.get('mcap_change') or 0:+.2f}% 24h)
• Volume 24h: ${(global_data.get('total_vol') or 0)/1e9:.1f}B
• BTC Dominance: {global_data.get('btc_dom', 0):.2f}%
"""
        send_text(gmsg.strip())
        time.sleep(1)

    for coin_id in COINS:
        print(f"\n--- {coin_id} ---")
        cg = get_coin(coin_id)
        if not cg.get("symbol"):
            continue
        msg = f"""
📊 *{cg.get('name')} ({cg.get('symbol')})*
• Price: ${cg.get('price', 0):,.2f}
• 24h: {cg.get('chg24') or 0:+.2f}%
• Market Cap: ${(cg.get('mcap') or 0)/1e9:.2f}B

_Debug message_
"""
        send_text(msg.strip())
        time.sleep(2)

    print("=== SELESAI ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FATAL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
