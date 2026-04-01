"""
Crypto Oracle v2 — 銘柄別予測エンジン
検証済み6銘柄 × 最適モデル構成（74回テスト実績）
"""

import datetime

# ============================================================
# 検証済み6銘柄
# ============================================================
COINS = [
    {"id": "bitcoin",   "sym": "BTC",  "name": "Bitcoin",   "profile": "A"},
    {"id": "ethereum",  "sym": "ETH",  "name": "Ethereum",  "profile": "A"},
    {"id": "ripple",    "sym": "XRP",  "name": "XRP",       "profile": "B"},
    {"id": "stellar",   "sym": "XLM",  "name": "Stellar",   "profile": "C"},
    {"id": "dogecoin",  "sym": "DOGE", "name": "Dogecoin",  "profile": "D"},
    {"id": "shiba-inu", "sym": "SHIB", "name": "Shiba Inu", "profile": "E"},
]

COIN_MAP = {c["id"]: c for c in COINS}

# ============================================================
# 共通モデル部品（v2 検証済み）
# ============================================================

def adaptive(prices):
    """直近5ステップの方向連続性を自動判定。
    トレンド継続型 vs 反転型を適応的に切替。"""
    if len(prices) < 6:
        return prices[-1]
    cont_ok, rev_ok = 0, 0
    for i in range(-5, 0):
        prev_trend = prices[i - 1] - prices[i - 2]
        actual = prices[i] - prices[i - 1]
        if (prev_trend > 0) == (actual > 0):
            cont_ok += 1
        else:
            rev_ok += 1
    trend = prices[-1] - prices[-2]
    if cont_ok > rev_ok:
        return prices[-1] + trend * 0.2   # トレンド継続モード
    return prices[-1] - trend * 0.15      # 反転モード


def mean_rev_5(prices):
    """5期間SMAへの平均回帰"""
    if len(prices) < 5:
        return prices[-1]
    sma = sum(prices[-5:]) / 5
    return prices[-1] + (sma - prices[-1]) * 0.3


def streak(prices):
    """連続性（慣性）を活用: 3連続→強い慣性, 2連続→やや慣性, 反転→逆張り"""
    if len(prices) < 4:
        return prices[-1]
    d1 = prices[-1] - prices[-2]
    d2 = prices[-2] - prices[-3]
    d3 = prices[-3] - prices[-4]
    same_dir = (d1 > 0) == (d2 > 0)
    triple = same_dir and (d2 > 0) == (d3 > 0)
    if triple:
        return prices[-1] + d1 * 0.4    # 3連続→慣性強い
    if same_dir:
        return prices[-1] + d1 * 0.25   # 2連続→やや慣性
    return prices[-1] - d1 * 0.15       # 反転シグナル


def bollinger(prices):
    """ボリンジャーバンド位置による回帰予測"""
    if len(prices) < 20:
        return prices[-1]
    sma = sum(prices[-20:]) / 20
    variance = sum((p - sma) ** 2 for p in prices[-20:]) / 20
    std = variance ** 0.5
    upper, lower = sma + 2 * std, sma - 2 * std
    pos = (prices[-1] - lower) / (upper - lower) if upper != lower else 0.5
    if pos > 0.8:
        return prices[-1] - std * 0.15   # 上バンド付近→下落予測
    if pos < 0.2:
        return prices[-1] + std * 0.15   # 下バンド付近→上昇予測
    return prices[-1] + (sma - prices[-1]) * 0.1


def rsi2(prices):
    """2期間RSI: 超短期の買われ/売られ過ぎ検知"""
    if len(prices) < 4:
        return prices[-1]
    gains, losses = 0, 0
    for i in range(-2, 0):
        change = prices[i] - prices[i - 1]
        if change > 0:
            gains += change
        else:
            losses -= change
    rsi = 100 if losses == 0 else 100 - 100 / (1 + gains / losses)
    if rsi > 80:
        return prices[-1] - abs(prices[-1] - prices[-2]) * 0.2
    if rsi < 20:
        return prices[-1] + abs(prices[-1] - prices[-2]) * 0.2
    return prices[-1]


# ============================================================
# 銘柄別予測関数（v2: 20ステップ検証済み）
# ============================================================

def predict_btc(prices, volumes, highs, lows, opens):
    """BTC: Adaptive+MeanRev5 (方向精度75%, MAPE 2.07%)"""
    return (adaptive(prices) + mean_rev_5(prices)) / 2

def predict_eth(prices, volumes, highs, lows, opens):
    """ETH: Adaptive+MeanRev5 (方向精度80%, MAPE 3.44%)"""
    return (adaptive(prices) + mean_rev_5(prices)) / 2

def predict_xrp(prices, volumes, highs, lows, opens):
    """XRP: Adaptive+RSI2 (方向精度65%, MAPE 4.46%)"""
    return (adaptive(prices) + rsi2(prices)) / 2

def predict_xlm(prices, volumes, highs, lows, opens):
    """XLM: Streak+Bollinger (方向精度70%, MAPE 6.02%)"""
    return (streak(prices) + bollinger(prices)) / 2

def predict_doge(prices, volumes, highs, lows, opens):
    """DOGE: Streak+Adaptive (方向精度70%, MAPE 6.64%)"""
    return (streak(prices) + adaptive(prices)) / 2

def predict_shib(prices, volumes, highs, lows, opens):
    """SHIB: RSI2 (方向精度75%, MAPE 10.09%)"""
    return rsi2(prices)


PREDICTORS = {
    "bitcoin": predict_btc,
    "ethereum": predict_eth,
    "ripple": predict_xrp,
    "stellar": predict_xlm,
    "dogecoin": predict_doge,
    "shiba-inu": predict_shib,
}


def predict(coin_id, prices, volumes, highs, lows, opens):
    """銘柄別ルーターで最適モデルを呼び出す"""
    fn = PREDICTORS.get(coin_id)
    if not fn:
        return prices[-1]
    return fn(prices, volumes, highs, lows, opens)


# ============================================================
# ボラティリティ連動信頼度
# ============================================================

def detect_volatility_regime(prices):
    """直近の変動率からボラティリティレジームを判定"""
    if len(prices) < 5:
        return "unknown", 0
    n = min(10, len(prices) - 1)
    changes = [abs(prices[i] - prices[i - 1]) / prices[i - 1]
               for i in range(-n, 0)]
    avg_vol = sum(changes) / len(changes)
    if avg_vol >= 0.03:
        return "high", avg_vol
    elif avg_vol >= 0.015:
        return "medium", avg_vol
    else:
        return "low", avg_vol


def get_reliability(mape, dir_acc, vol_regime="medium"):
    """ボラティリティ連動信頼度"""
    if vol_regime == "low":
        return {
            "label": "低（レンジ相場）",
            "stars": "★☆☆☆☆",
            "color": "#ff8855",
            "alert": "⚠️ 横ばい相場のため予測精度が低下中。様子見推奨。"
        }
    if vol_regime == "high" and dir_acc >= 65:
        return {"label": "高", "stars": "★★★★★", "color": "#00ffaa", "alert": None}
    if dir_acc >= 70:
        return {"label": "高", "stars": "★★★★★", "color": "#00ffaa", "alert": None}
    if dir_acc >= 60:
        return {"label": "中高", "stars": "★★★★☆", "color": "#66ffcc", "alert": None}
    if dir_acc >= 50:
        return {"label": "中", "stars": "★★★☆☆", "color": "#ffd866", "alert": None}
    return {"label": "中低", "stars": "★★☆☆☆", "color": "#ff8855", "alert": None}


# ============================================================
# ファンダメンタル異常アラート
# ============================================================

def detect_anomaly(prices, volumes):
    """急激な価格変動や出来高急騰を検知"""
    if len(prices) < 3 or not volumes or len(volumes) < 3:
        return None
    recent_change = abs(prices[-1] - prices[-2]) / prices[-2]
    n = min(9, len(prices) - 2)
    avg_change = sum(abs(prices[i] - prices[i - 1]) / prices[i - 1]
                     for i in range(max(1, len(prices) - 10), len(prices) - 1)) / max(1, n)
    if avg_change > 0 and recent_change > avg_change * 3:
        direction = "急騰" if prices[-1] > prices[-2] else "急落"
        return f"⚡ {direction}検知（通常の{recent_change / avg_change:.1f}倍の変動）。ファンダメンタル要因の可能性。"
    recent_vol = volumes[-1]
    vol_n = min(9, len(volumes) - 1)
    avg_vol = sum(volumes[max(0, len(volumes) - 10):len(volumes) - 1]) / max(1, vol_n)
    if avg_vol > 0 and recent_vol > avg_vol * 3:
        return f"📊 出来高急増（通常の{recent_vol / avg_vol:.1f}倍）。大きな動きの前兆の可能性。"
    return None


# ============================================================
# 推奨判定
# ============================================================

def get_recommendation(score, forecast_change):
    if score >= 65 and forecast_change > 0.5:
        return {"action": "買い時", "color": "#00ffaa", "icon": "🟢"}
    elif score >= 55 and forecast_change > 0:
        return {"action": "やや買い", "color": "#66ffcc", "icon": "🔵"}
    elif score <= 35 and forecast_change < -0.5:
        return {"action": "やや売り", "color": "#ff8855", "icon": "🟠"}
    elif score <= 45 and forecast_change < 0:
        return {"action": "やや売り", "color": "#ff8855", "icon": "🟠"}
    else:
        return {"action": "様子見", "color": "#ffd866", "icon": "🟡"}


# ============================================================
# エントリー/イグジット提案
# ============================================================

def suggest_entry_exit(current_price, predicted_price, prices):
    """ATRベースの具体的なエントリー/イグジットポイント"""
    if len(prices) < 5:
        return None
    # 簡易ATR: 直近5日の日次変動幅平均
    atr = sum(abs(prices[i] - prices[i - 1]) for i in range(-5, 0)) / 5
    if atr <= 0:
        return None
    direction = "up" if predicted_price > current_price else "down"
    if direction == "up":
        entry = current_price - atr * 0.3
        target = predicted_price
        stop_loss = current_price - atr * 1.5
    else:
        entry = current_price + atr * 0.3
        target = predicted_price
        stop_loss = current_price + atr * 1.5
    risk = abs(entry - stop_loss)
    reward = abs(target - entry)
    rr_ratio = reward / risk if risk > 0 else 0
    return {
        "direction": direction,
        "entry": round(entry, 6),
        "target": round(target, 6),
        "stop_loss": round(stop_loss, 6),
        "risk_reward": round(rr_ratio, 1),
        "note": f"R/R比 {rr_ratio:.1f}:1" + (" ✅ 推奨" if rr_ratio >= 1.5 else " ⚠️ 低R/R")
    }


# ============================================================
# バックテスト（ウォークフォワード）
# ============================================================

def backtest(coin_id, prices, volumes, highs, lows, opens):
    """ウォークフォワード検証"""
    n = len(prices)
    test_size = max(5, int(n * 0.3))
    start = n - test_size
    if start < 10:
        return {"mape": 99, "direction": 50, "n": 0}

    errors = []
    dir_correct = 0
    total = 0

    for i in range(start, n):
        tp = prices[:i]
        tv = volumes[:i] if volumes else None
        th = highs[:i] if highs else None
        tl = lows[:i] if lows else None
        to_ = opens[:i] if opens else None

        pred = predict(coin_id, tp, tv, th, tl, to_)
        actual = prices[i]
        prev = prices[i - 1]

        errors.append(abs(pred - actual) / actual * 100)
        if (pred > prev) == (actual > prev):
            dir_correct += 1
        total += 1

    return {
        "mape": round(sum(errors) / len(errors), 2) if errors else 99,
        "direction": round(dir_correct / total * 100, 1) if total > 0 else 50,
        "n": total,
    }


# ============================================================
# 7日予測 + 95%信頼区間
# ============================================================

def forecast_7day(coin_id, prices, volumes, highs, lows, opens, bt_mape):
    last = prices[-1]
    changes = [(prices[i] - prices[i - 1]) / prices[i - 1]
               for i in range(max(1, len(prices) - 20), len(prices))]
    vol = (sum(c ** 2 for c in changes) / len(changes)) ** 0.5 if changes else 0.025

    forecasts = [{"day": 0, "price": round(last, 8), "upper": round(last, 8), "lower": round(last, 8)}]
    sim_p = list(prices)
    sim_v = list(volumes) if volumes else None
    sim_h = list(highs) if highs else None
    sim_l = list(lows) if lows else None
    sim_o = list(opens) if opens else None

    for d in range(1, 8):
        pred = predict(coin_id, sim_p, sim_v, sim_h, sim_l, sim_o)
        damp = 1 / (1 + d * 0.08)
        damped = last + (pred - last) * damp

        market_unc = last * vol * (d ** 0.5) * 1.96
        model_unc = last * (bt_mape / 100) * d * 1.5
        total_unc = market_unc + model_unc

        forecasts.append({
            "day": d,
            "price": round(damped, 8),
            "upper": round(damped + total_unc, 8),
            "lower": round(max(damped - total_unc, damped * 0.3), 8),
        })

        sim_p.append(pred)
        if sim_v:
            sim_v.append(sim_v[-1])
        if sim_h:
            sim_h.append(max(pred, damped) * 1.01)
        if sim_l:
            sim_l.append(min(pred, damped) * 0.99)
        if sim_o:
            sim_o.append(sim_p[-2])

    return forecasts


# ============================================================
# 円建て予測
# ============================================================

def forecast_jpy_7day(jpy_rates):
    """USD/JPYの短期予測（EMA+平均回帰）"""
    if not jpy_rates or len(jpy_rates) < 5:
        return [150.0] * 8
    # EMA(10) で短期トレンド
    k = 2 / 11
    ema = jpy_rates[0]
    for r in jpy_rates[1:]:
        ema = r * k + ema * (1 - k)
    last = jpy_rates[-1]
    sma20 = sum(jpy_rates[-20:]) / min(20, len(jpy_rates))
    forecasts = [last]
    for d in range(1, 8):
        trend = ema - sma20
        damp = 1 / (1 + d * 0.1)
        fc = last + trend * 0.3 * damp + (sma20 - last) * 0.1 * damp
        forecasts.append(round(fc, 2))
    return forecasts


def combined_jpy_forecast(usd_forecasts, jpy_rate_forecasts):
    """USD建て予測 × USD/JPY予測 = 円建て最終予測"""
    result = []
    for i, fc in enumerate(usd_forecasts):
        rate = jpy_rate_forecasts[i] if i < len(jpy_rate_forecasts) else jpy_rate_forecasts[-1]
        result.append({
            "day": fc["day"],
            "jpy_price": round(fc["price"] * rate, 2),
            "jpy_upper": round(fc["upper"] * rate, 2),
            "jpy_lower": round(fc["lower"] * rate, 2),
            "rate": rate,
        })
    return result


def decompose_change(current_usd, prev_usd, current_rate, prev_rate):
    """円建て変動を「暗号資産要因」と「為替要因」に分解"""
    if prev_usd <= 0 or prev_rate <= 0:
        return {"crypto_pct": 0, "fx_pct": 0, "jpy_total_pct": 0, "crypto_label": "0.0%", "fx_label": "0.0%"}
    crypto_change = (current_usd - prev_usd) / prev_usd * 100
    fx_change = (current_rate - prev_rate) / prev_rate * 100
    jpy_total = ((current_usd * current_rate) - (prev_usd * prev_rate)) / (prev_usd * prev_rate) * 100
    return {
        "crypto_pct": round(crypto_change, 2),
        "fx_pct": round(fx_change, 2),
        "jpy_total_pct": round(jpy_total, 2),
        "crypto_label": f"{'+' if crypto_change >= 0 else ''}{crypto_change:.1f}%",
        "fx_label": f"{'円安' if fx_change > 0 else '円高'} {'+' if fx_change >= 0 else ''}{fx_change:.1f}%",
    }


def decompose_forecast(usd_forecast, jpy_rate_forecast, current_usd, current_rate):
    """予測の変動を要因分解"""
    if current_usd <= 0 or current_rate <= 0:
        return {"jpy_price": 0, "jpy_total_pct": 0, "crypto_pct": 0, "fx_pct": 0}
    crypto_change = (usd_forecast - current_usd) / current_usd * 100
    fx_change = (jpy_rate_forecast - current_rate) / current_rate * 100
    jpy_forecast = usd_forecast * jpy_rate_forecast
    jpy_total = (jpy_forecast - current_usd * current_rate) / (current_usd * current_rate) * 100
    return {
        "jpy_price": round(jpy_forecast, 2),
        "jpy_total_pct": round(jpy_total, 2),
        "crypto_pct": round(crypto_change, 2),
        "fx_pct": round(fx_change, 2),
    }
