"""Crypto Oracle AI v2 — Flask server"""

import os
import logging
from flask import Flask, render_template, jsonify, request
from data_fetcher import (
    get_ohlcv, get_current_prices, get_current_jpy_rate,
    get_jpy_history, get_chart_data, COINS,
)
from prediction_engine import (
    predict, backtest, forecast_7day, get_reliability,
    get_recommendation, detect_volatility_regime, detect_anomaly,
    suggest_entry_exit, forecast_jpy_7day, combined_jpy_forecast,
    decompose_change, decompose_forecast,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html", coins=COINS)


@app.route("/api/coins")
def coins_list():
    return jsonify(COINS)


@app.route("/api/data/<coin_id>")
def get_coin_data(coin_id):
    ohlcv = get_ohlcv(coin_id)
    if not ohlcv:
        return jsonify({"error": "データ取得失敗"}), 500

    p = ohlcv["prices"]
    v = ohlcv["volumes"]
    h = ohlcv["highs"]
    l = ohlcv["lows"]
    o = ohlcv["opens"]
    dates = ohlcv["dates"]

    bt = backtest(coin_id, p, v, h, l, o)
    fc = forecast_7day(coin_id, p, v, h, l, o, bt["mape"])

    # ボラティリティレジーム
    vol_regime, vol_value = detect_volatility_regime(p)
    rel = get_reliability(bt["mape"], bt["direction"], vol_regime)

    # 異常検知
    anomaly = detect_anomaly(p, v)

    last = p[-1]
    fc_change = ((fc[-1]["price"] - last) / last) * 100
    day1_change = ((fc[1]["price"] - last) / last) * 100
    confidence = max(0, min(100, 100 - bt["mape"] * 10))
    score = confidence * 0.4 + bt["direction"] * 0.4 + (60 if fc_change > 0 else 40) * 0.2

    # 横ばい時はスコアを控えめに
    if vol_regime == "low":
        score = min(score, 50)

    rec = get_recommendation(score, fc_change)

    # エントリー/イグジット提案
    entry_exit = suggest_entry_exit(last, fc[1]["price"], p)

    # 円建て予測
    jpy_rates = get_jpy_history(60)
    current_rate = get_current_jpy_rate()
    jpy_fc = forecast_jpy_7day(jpy_rates) if jpy_rates else [current_rate] * 8
    jpy_combined = combined_jpy_forecast(fc, jpy_fc)

    # 要因分解
    prev_usd = p[-2] if len(p) >= 2 else p[-1]
    prev_rate = jpy_rates[-2] if jpy_rates and len(jpy_rates) >= 2 else current_rate
    decomp = decompose_change(p[-1], prev_usd, current_rate, prev_rate)

    # 予測の要因分解
    fc_decomp = decompose_forecast(fc[1]["price"], jpy_fc[1] if len(jpy_fc) > 1 else current_rate,
                                    p[-1], current_rate)

    return jsonify({
        "prices": p,
        "volumes": v,
        "highs": h,
        "lows": l,
        "opens": o,
        "dates": dates,
        "backtest": bt,
        "forecast": fc,
        "reliability": rel,
        "recommendation": rec,
        "score": round(score, 1),
        "fc_change": round(fc_change, 2),
        "day1_change": round(day1_change, 2),
        "vol_regime": vol_regime,
        "vol_value": round(vol_value * 100, 2) if vol_value else 0,
        "anomaly": anomaly,
        "entry_exit": entry_exit,
        "jpy_rate": current_rate,
        "jpy_forecasts": jpy_combined,
        "decomposition": decomp,
        "forecast_decomposition": fc_decomp,
    })


@app.route("/api/chart/<coin_id>")
def get_chart(coin_id):
    tf = request.args.get("tf", "1d")
    period = request.args.get("period", "3m")
    cur = request.args.get("cur", "usd")
    data = get_chart_data(coin_id, tf, period)
    if not data:
        return jsonify({"error": "データ取得失敗"}), 500
    if cur == "jpy":
        rate = get_current_jpy_rate()
        for c in data["candles"]:
            c["open"] *= rate
            c["high"] *= rate
            c["low"] *= rate
            c["close"] *= rate
    return jsonify(data)


@app.route("/api/prices")
def get_all_prices():
    return jsonify(get_current_prices())


@app.route("/api/rate")
def get_rate():
    return jsonify({"rate": get_current_jpy_rate()})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
