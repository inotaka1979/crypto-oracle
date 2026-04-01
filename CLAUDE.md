# Crypto Oracle AI v2

## 概要
仮想通貨価格予測Webアプリ。Flask + Chart.js + 銘柄別最適MLモデル。
検証済み6銘柄のみ（BTC, ETH, XRP, XLM, DOGE, SHIB）。

## 構成
- app.py: Flask サーバー
- prediction_engine.py: 銘柄別予測エンジン（Adaptive/MeanRev5/Streak/Bollinger/RSI2）
- data_fetcher.py: CoinGecko API + USD/JPY + チャートデータ
- templates/index.html: モバイルファースト・ダークUI
- render.yaml: Render.comデプロイ設定

## 予測モデル（74回テスト検証済み）
| 銘柄 | モデル | 方向精度 | MAPE |
|------|--------|---------|------|
| BTC  | Adaptive+MeanRev5 | 75% | 2.07% |
| ETH  | Adaptive+MeanRev5 | 80% | 3.44% |
| XRP  | Adaptive+RSI2 | 65% | 4.46% |
| XLM  | Streak+Bollinger | 70% | 6.02% |
| DOGE | Streak+Adaptive | 70% | 6.64% |
| SHIB | RSI2 | 75% | 10.09% |

## 機能
- ボラティリティ連動信頼度（横ばいアラート）
- ファンダメンタル異常検知（急騰/急落/出来高急増）
- 円建て表示 + 要因分解（暗号資産 vs 為替）
- エントリー/イグジット提案（ATRベース）
- 予測履歴の自動検証（localStorage）
- 7日予測 + 95%信頼区間

## 起動
```bash
pip install -r requirements.txt
python app.py
```

## API
- GET / — メインUI
- GET /api/data/<coin_id> — OHLCV + 予測 + 信頼度 + 要因分解
- GET /api/chart/<coin_id>?tf=1d&period=3m&cur=usd — チャートデータ
- GET /api/prices — 全銘柄現在価格
- GET /api/rate — USD/JPYレート

## デプロイ
Render.com（無料プラン）にpushでデプロイ。
