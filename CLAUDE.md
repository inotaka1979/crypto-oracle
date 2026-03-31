# Crypto Oracle AI

## プロジェクト概要
仮想通貨価格予測PWAアプリ。9モデルアンサンブルで13銘柄の価格を予測。
GitHub Pagesでホスティング。

## 技術構成
- 単一HTML（index.html）にJS/CSS全て内包
- PWA対応（manifest.json + apple-mobile-web-app）
- GitHub Pages でホスティング
- 外部API: CoinGecko（CORS対応済み、無料版）

## 対象銘柄
BTC, ETH, XRP, XLM, DOGE, SHIB, SOL, ADA, AVAX, DOT, LINK, TRX, SUI（+ USD/JPY）

## 予測モデル（9モデルアンサンブル）
1. S/R Level - サポート/レジスタンスレベル
2. ATR - Average True Range
3. EMA Cross - 指数移動平均クロス
4. OBV Trend - On-Balance Volume
5. VWAP Revert - 出来高加重平均回帰
6. Candlestick - ローソク足パターン
7. RSI+Vol - RSI+出来高加重
8. Vol Regime - ボラティリティレジーム
9. Seasonal - 月次季節性+半減期

## デプロイ手順
1. index.html を編集
2. git add -A
3. git commit -m "変更内容を日本語で記載"
4. git push origin main
5. 1-3分後にGitHub Pagesに自動反映

## コミットメッセージ規約
- feat: 新機能追加
- fix: バグ修正
- update: パラメータ調整、データ更新
- docs: ドキュメント更新

## 注意事項
- index.htmlは単一ファイル構成を維持すること
- 外部APIはCORS対応のもののみ使用
- CoinGecko無料版: 10-30 req/min 制限
- 画像等のアセットはリポジトリルートに配置
