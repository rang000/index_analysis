# index_analysis

## Streamlit app

主要指数の価格、出来高、四半期別pain pointを表示するStreamlitアプリです。

## Features

- Yahoo Financeから日次データを取得
- 対象期間は `2020-01-01` から `2026-05-01`
- 初回表示時にデータを取得し、Streamlitのキャッシュに保持
- Bloomberg端末風の黒基調UI
- 価格チャートと出来高バーを表示
- 表示期間スライダーでチャート範囲を変更
- プリセット指数を選択可能
  - Nikkei 225: `^N225`
  - S&P 500: `^GSPC`
  - NASDAQ Composite: `^IXIC`
  - NASDAQ 100: `^NDX`
  - Dow Jones: `^DJI`
  - TOPIX: `^TOPX`
  - FTSE 100: `^FTSE`
  - DAX: `^GDAXI`
  - Hang Seng: `^HSI`
- 任意のYahoo Financeティッカーも入力可能
- pain pointチャート用の株価表示期間を個別に指定可能
- pain point開始日は直近4四半期の期初、または任意の日付リストを指定可能
- Trend-followers net positionを価格系列から推計
- pain pointは推計positionの増加分で加重した平均取得水準
- Option chainからgamma exposure profileを推計
- 取得データテーブルで選択行の列方向集計を表示

## Pain Point

Sidebarの `Pain Point` で、pain pointチャートだけに使う株価期間と開始日を指定します。

`Price start` と `Price end` で、pain pointチャートに表示する株価期間を指定します。

`Pain starts` は2種類あります。

- `Quarter starts`: `Price end` から見た直近4四半期の期初をposition開始日として扱います。
- `Custom dates`: 任意の日付を1行に1日、またはカンマ区切りで指定します。

指定した開始日が休場日の場合は、その日以降の最初の取引日を開始日とします。
Trend-followers net positionは、複数期間の価格モメンタムをボラティリティで正規化して `-1` から `+1` のscoreにした推計値です。
実際の投資主体別建玉データではなく、価格系列から作ったproxyです。

各cohortのpain pointは、cohort開始日以降に推計positionが増えた分だけを新規建玉として扱い、その増加分で `Close` を加重平均した水準です。
単純なClose累積平均ではないため、Trend-followersが上昇局面で追加的にlongを積んだ価格帯がより強く反映されます。

## Gamma Exposure

Sidebarの `Gamma Exposure > Show gamma exposure` を有効にすると、option chainからスポット水準別のgamma exposureを表示します。

`Option ticker` にはYahoo Financeでoption chainを取得できるティッカーを指定します。
SPX指数そのもののoption chainが取得できない場合があるため、S&P 500ではデフォルトを `SPY` にしています。
データ取得はまず `yfinance` を使い、失敗した場合はYahoo Financeのoption APIへ直接アクセスするフォールバックを使います。

計算はBlack-Scholes gammaを使い、open interestとcontract sizeを掛けて、スポットが1%動いたときのgamma dollar exposureを `$bn` 単位で表示します。
符号はcallをプラス、putをマイナスとして扱います。

このgamma exposureはYahoo Financeのoption chainを使った推計です。
正式なディーラーgammaや顧客/ディーラーの実ポジションを直接表すものではありません。

## Data Table Summary

`取得データ` セクションでは、Excelのステータスバーに近い集計を表示します。

1. `集計列` で `High` や `Close` などの数値列を選択
2. テーブル左端のチェックボックスで集計したい行を選択
3. 選択行のうち、`集計列` のセルだけについて以下を表示
   - Count
   - Sum
   - Average
   - Min
   - Max

Streamlit標準の `st.dataframe` はドラッグしたセル範囲をPython側へ返さないため、依存追加なしの実装では「集計列 + 選択行」の組み合わせで列方向のセル集計を行います。

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Requirements

```txt
streamlit==1.50.0
yfinance==1.2.0
pandas==2.3.3
requests==2.32.5
```
