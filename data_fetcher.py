"""CoinGecko API data fetcher — 検証済み6銘柄 + USD/JPY + チャートデータ"""

import time
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

# 検証済み6銘柄のみ
COINS = [
    {"id": "bitcoin",   "sym": "BTC",  "name": "Bitcoin",   "profile": "A"},
    {"id": "ethereum",  "sym": "ETH",  "name": "Ethereum",  "profile": "A"},
    {"id": "ripple",    "sym": "XRP",  "name": "XRP",       "profile": "B"},
    {"id": "stellar",   "sym": "XLM",  "name": "Stellar",   "profile": "C"},
    {"id": "dogecoin",  "sym": "DOGE", "name": "Dogecoin",  "profile": "D"},
    {"id": "shiba-inu", "sym": "SHIB", "name": "Shiba Inu", "profile": "E"},
]

COIN_MAP = {c["id"]: c for c in COINS}

BASE_URL = "https://api.coingecko.com/api/v3"
CACHE_TTL = 120
PRICE_CACHE_TTL = 60
RATE_CACHE_TTL = 300

_last_api_call = 0
_ohlcv_cache = {}
_price_cache = {"data": None, "timestamp": 0}
_rate_cache = {"data": None, "timestamp": 0}
_jpy_history_cache = {"data": None, "timestamp": 0}
_chart_cache = {}


def _api_get(url, params=None, retries=5, backoff=3):
    """GET request with retry, backoff, and global rate limiting."""
    global _last_api_call
    elapsed = time.time() - _last_api_call
    if elapsed < 2.0:
        time.sleep(2.0 - elapsed)

    for attempt in range(retries):
        try:
            _last_api_call = time.time()
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 429:
                wait = backoff * (2 ** attempt)
                logger.warning("Rate limited, waiting %ds (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("API request failed (attempt %d): %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    return None


def get_ohlcv(coin_id):
    """180日分の日足OHLCVデータを取得"""
    now = time.time()
    if coin_id in _ohlcv_cache and now - _ohlcv_cache[coin_id]["timestamp"] < CACHE_TTL:
        return _ohlcv_cache[coin_id]["data"]

    market = _api_get(f"{BASE_URL}/coins/{coin_id}/market_chart",
                      {"vs_currency": "usd", "days": 180})
    if not market or "prices" not in market:
        return None

    daily = {}
    for ts, price in market["prices"]:
        day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        if day not in daily:
            daily[day] = {"open": price, "high": price, "low": price,
                          "close": price, "volume": 0}
        else:
            daily[day]["close"] = price
            daily[day]["high"] = max(daily[day]["high"], price)
            daily[day]["low"] = min(daily[day]["low"], price)

    if "total_volumes" in market:
        for ts, vol in market["total_volumes"]:
            day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            if day in daily:
                daily[day]["volume"] += vol

    # 直近30日のOHLCを上書き（より正確）
    ohlc = _api_get(f"{BASE_URL}/coins/{coin_id}/ohlc",
                    {"vs_currency": "usd", "days": 30}, retries=2, backoff=2)
    if ohlc:
        ohlc_daily = {}
        for row in ohlc:
            ts, o, h, l, c = row
            day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
            if day not in ohlc_daily:
                ohlc_daily[day] = {"open": o, "high": h, "low": l, "close": c}
            else:
                ohlc_daily[day]["close"] = c
                ohlc_daily[day]["high"] = max(ohlc_daily[day]["high"], h)
                ohlc_daily[day]["low"] = min(ohlc_daily[day]["low"], l)
        for day, d in ohlc_daily.items():
            if day in daily:
                daily[day]["open"] = d["open"]
                daily[day]["high"] = d["high"]
                daily[day]["low"] = d["low"]
                daily[day]["close"] = d["close"]

    sorted_days = sorted(daily.keys())
    if not sorted_days:
        return None

    data = {
        "prices": [daily[d]["close"] for d in sorted_days],
        "volumes": [daily[d]["volume"] for d in sorted_days],
        "highs": [daily[d]["high"] for d in sorted_days],
        "lows": [daily[d]["low"] for d in sorted_days],
        "opens": [daily[d]["open"] for d in sorted_days],
        "dates": sorted_days,
    }

    _ohlcv_cache[coin_id] = {"data": data, "timestamp": now}
    logger.info("Fetched OHLCV for %s: %d days", coin_id, len(sorted_days))
    return data


def get_current_prices():
    """全銘柄の現在価格(USD/JPY)"""
    now = time.time()
    if _price_cache["data"] and now - _price_cache["timestamp"] < PRICE_CACHE_TTL:
        return _price_cache["data"]

    ids = ",".join(c["id"] for c in COINS)
    data = _api_get(f"{BASE_URL}/simple/price", {
        "ids": ids,
        "vs_currencies": "usd,jpy",
        "include_24hr_change": "true",
    })
    if data:
        _price_cache["data"] = data
        _price_cache["timestamp"] = now
    return data or _price_cache["data"] or {}


def get_current_jpy_rate():
    """現在のUSD/JPYレートを取得"""
    now = time.time()
    if _rate_cache["data"] and now - _rate_cache["timestamp"] < RATE_CACHE_TTL:
        return _rate_cache["data"]

    data = _api_get(f"{BASE_URL}/simple/price", {
        "ids": "usd-coin",
        "vs_currencies": "jpy",
    })
    if data and "usd-coin" in data:
        rate = data["usd-coin"].get("jpy", 150)
    else:
        rate = 150
    _rate_cache["data"] = rate
    _rate_cache["timestamp"] = now
    return rate


def get_jpy_history(days=60):
    """BTC/USD と BTC/JPY の比率からUSD/JPY履歴を算出"""
    now = time.time()
    if _jpy_history_cache["data"] and now - _jpy_history_cache["timestamp"] < 600:
        return _jpy_history_cache["data"]

    usd = _api_get(f"{BASE_URL}/coins/bitcoin/market_chart",
                   {"vs_currency": "usd", "days": days}, retries=2)
    jpy = _api_get(f"{BASE_URL}/coins/bitcoin/market_chart",
                   {"vs_currency": "jpy", "days": days}, retries=2)

    if not usd or not jpy or "prices" not in usd or "prices" not in jpy:
        return None

    # 日次平均でマッチ
    usd_daily = {}
    for ts, p in usd["prices"]:
        day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        usd_daily[day] = p
    jpy_daily = {}
    for ts, p in jpy["prices"]:
        day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        jpy_daily[day] = p

    rates = []
    for day in sorted(usd_daily.keys()):
        if day in jpy_daily and usd_daily[day] > 0:
            rates.append(jpy_daily[day] / usd_daily[day])

    if rates:
        _jpy_history_cache["data"] = rates
        _jpy_history_cache["timestamp"] = now
    return rates or None


def get_chart_data(coin_id, tf="1d", period="3m"):
    """チャート用データ（時間足・期間対応）"""
    cache_key = f"{coin_id}_{tf}_{period}"
    now = time.time()
    if cache_key in _chart_cache and now - _chart_cache[cache_key]["timestamp"] < CACHE_TTL:
        return _chart_cache[cache_key]["data"]

    # 期間→日数マッピング
    period_days = {"1d": 1, "1w": 7, "1m": 30, "3m": 90, "1y": 365}
    days = period_days.get(period, 90)

    if tf == "1h" and days <= 1:
        # 1時間足×1日: market_chart
        raw = _api_get(f"{BASE_URL}/coins/{coin_id}/market_chart",
                       {"vs_currency": "usd", "days": 1})
        if not raw or "prices" not in raw:
            return None
        candles = []
        hourly = {}
        for ts, price in raw["prices"]:
            hour_key = (ts // 3600000) * 3600000
            if hour_key not in hourly:
                hourly[hour_key] = {"open": price, "high": price, "low": price, "close": price}
            else:
                hourly[hour_key]["close"] = price
                hourly[hour_key]["high"] = max(hourly[hour_key]["high"], price)
                hourly[hour_key]["low"] = min(hourly[hour_key]["low"], price)
        for ts in sorted(hourly.keys()):
            d = hourly[ts]
            candles.append({"time": ts, "open": d["open"], "high": d["high"],
                            "low": d["low"], "close": d["close"]})
    else:
        # OHLC API
        raw = _api_get(f"{BASE_URL}/coins/{coin_id}/ohlc",
                       {"vs_currency": "usd", "days": days}, retries=3)
        if not raw:
            return None
        candles = []
        if tf == "1w":
            # 週足集約
            weekly = {}
            for row in raw:
                ts, o, h, l, c = row
                week_start = (ts // (7 * 86400000)) * (7 * 86400000)
                if week_start not in weekly:
                    weekly[week_start] = {"open": o, "high": h, "low": l, "close": c}
                else:
                    weekly[week_start]["close"] = c
                    weekly[week_start]["high"] = max(weekly[week_start]["high"], h)
                    weekly[week_start]["low"] = min(weekly[week_start]["low"], l)
            for ts in sorted(weekly.keys()):
                d = weekly[ts]
                candles.append({"time": ts, "open": d["open"], "high": d["high"],
                                "low": d["low"], "close": d["close"]})
        elif tf == "4h":
            # 4時間足集約
            four_hourly = {}
            for row in raw:
                ts, o, h, l, c = row
                key = (ts // (4 * 3600000)) * (4 * 3600000)
                if key not in four_hourly:
                    four_hourly[key] = {"open": o, "high": h, "low": l, "close": c}
                else:
                    four_hourly[key]["close"] = c
                    four_hourly[key]["high"] = max(four_hourly[key]["high"], h)
                    four_hourly[key]["low"] = min(four_hourly[key]["low"], l)
            for ts in sorted(four_hourly.keys()):
                d = four_hourly[ts]
                candles.append({"time": ts, "open": d["open"], "high": d["high"],
                                "low": d["low"], "close": d["close"]})
        else:
            # 日足そのまま
            daily = {}
            for row in raw:
                ts, o, h, l, c = row
                day_key = (ts // 86400000) * 86400000
                if day_key not in daily:
                    daily[day_key] = {"open": o, "high": h, "low": l, "close": c}
                else:
                    daily[day_key]["close"] = c
                    daily[day_key]["high"] = max(daily[day_key]["high"], h)
                    daily[day_key]["low"] = min(daily[day_key]["low"], l)
            for ts in sorted(daily.keys()):
                d = daily[ts]
                candles.append({"time": ts, "open": d["open"], "high": d["high"],
                                "low": d["low"], "close": d["close"]})

    data = {"candles": candles}
    _chart_cache[cache_key] = {"data": data, "timestamp": now}
    return data
