# fitbit-cli

Google Health API (`https://health.googleapis.com/v4`) から自分の睡眠・歩数・健康指標を取得し、
日付フォルダに JSON で保存する CLI です。タイムゾーンは Asia/Tokyo（JST）固定です。
手動で実行する CLI で、定期実行の仕組みは含みません。

## 構成

```text
fitbit-cli/
├─ src/
│  ├─ auth.py                  Refresh Token → Access Token
│  ├─ google_health_client.py  共通の API 呼び出し・日付処理・JSON 保存
│  ├─ fetch_sleep.py           睡眠
│  ├─ fetch_steps.py           歩数
│  ├─ fetch_health_metrics.py  心拍・安静時心拍・SpO2・HRV・呼吸数・体重
│  ├─ main.py                  上の 3 つを順に実行
│  └─ plot_sleep.py            保存した睡眠データからグラフ(HTML)を作る
├─ data/                       取得結果（Git 管理外）
├─ .env.example
├─ requirements.txt
└─ README.md
```

## セットアップ

Python 3.12 が必要です。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`.env.example` を `.env` にコピーして値を設定します。

```powershell
Copy-Item .env.example .env
```

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=
```

`.env` が無くても、同名の OS 環境変数があればそれを使います。
両方ある場合は OS 環境変数が優先されます。

### Refresh Token の取得

[OAuth 2.0 Playground](https://developers.google.com/oauthplayground) で取得します。

1. 右上の歯車で **Use your own OAuth credentials** にチェックし、自分の Client ID / Secret を入力、Access type は **Offline**
2. 下記 3 つの scope をスペース区切りで入力して認可
3. **Exchange authorization code for tokens** で出た Refresh Token を `.env` に設定

```text
https://www.googleapis.com/auth/googlehealth.sleep.readonly
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
```

Cloud Console 側の前提:

- Google Health API を有効化
- OAuth クライアント（ウェブ アプリケーション）に、承認済みリダイレクト URI `https://developers.google.com/oauthplayground` を登録
- 同意画面が「テスト」の間は、自分をテストユーザーに追加する。また、この状態の Refresh Token は
  **7 日で失効**する（[公式](https://developers.google.com/identity/protocols/oauth2)）

## 実行方法

```powershell
python src/main.py
```

個別に実行することもできます。日付（`YYYY-MM-DD`、JST）を指定すると、その日のデータを取得し、`data/<その日>/` に保存します。

```powershell
python src/fetch_sleep.py [YYYY-MM-DD]
python src/fetch_steps.py [YYYY-MM-DD]
python src/fetch_health_metrics.py
python src/plot_sleep.py [YYYY-MM-DD]   # 保存済みの sleep.json から sleep.html を作る（API は呼ばない）
python src/auth.py                      # Access Token が取得できるかの確認（値は表示しない）
```

`main.py` は 1 つの取得が失敗しても残りを続行し、失敗があれば終了コード 1 で終わります。

Claude Code から「昨日の睡眠を教えて」のように頼むと、上のスクリプトを日付付きで実行して結果を答えてくれます。
トークンはスクリプトが `.env` から読むので、会話に貼る必要はありません。

## 取得内容と保存先

保存先は `data/<実行日(JST)>/` で、同じ日に再実行すると上書きされます（UTF-8・インデント付き）。

| ファイル | 内容 | 対象期間（日付を省略したとき） |
| --- | --- | --- |
| `sleep.json` | 睡眠セッション（開始/終了、Awake/Light/Deep/REM） | 実行日に**終了**した睡眠（＝今朝起きた前夜の睡眠） |
| `steps.json` | 1 分単位の生データ `dataPoints` と日次合計 `dailyRollUp` | 昨日 1 日分 |
| `health_metrics.json` | 心拍・安静時心拍・SpO2・HRV・呼吸数・体重 | 下記 |

`health_metrics.json` の指標（`src/fetch_health_metrics.py` の `METRICS`）:

| 指標 | dataType | 内容 / 対象期間 |
| --- | --- | --- |
| heart_rate | `heart-rate` | dailyRollUp（平均/最小/最大）、昨日 |
| resting_heart_rate | `daily-resting-heart-rate` | 昨日〜今日 |
| spo2 | `daily-oxygen-saturation` | 昨日〜今日 |
| hrv | `daily-heart-rate-variability` | 昨日〜今日 |
| respiratory_rate | `daily-respiratory-rate` | 昨日〜今日 |
| weight | `weight` | 直近 30 日（記録がなければ空） |

指標を増やすときは `METRICS` に 1 行追加します。dataType 名は
[公式リファレンス](https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints)
で確認してください。

## 注意点（実データで確認したこと）

- **歩数は `dailyRollUp` の値を使います。** Fitbit とスマホ（Health Connect）の両方が同じ歩行を記録するため、
  生データの単純合計は二重計上になります。
  それでも Fitbit アプリの表示とは数十歩ずれることがあります。
- 心拍の生データは 1 日 3 万件超（約 26MB）になるため、保存は日次集計のみです。
  アプリの心拍の範囲は 5 分程度の平均に近く、日次集計の最小・最大（生データの値）とは一致しません。
- 日次サマリ（安静時心拍・HRV・呼吸数）は起床した日の日付で入り、SpO2 は前日付けで入ることがあります。
- 睡眠スコアは API から取得できません（レスポンスに項目がありません）。
- 睡眠の `pageSize` 上限は 25 です。
- API のレスポンスは Google 側の仕様変更で変わる可能性があります。解析できない形はスキップし、raw JSON は必ず保存します。

## トラブルシューティング

| 症状 | 原因と対処 |
| --- | --- |
| `No time zone found with key Asia/Tokyo` | Windows に IANA のタイムゾーンデータがない。`pip install -r requirements.txt` で `tzdata` を入れる |
| 日本語のエラーメッセージが文字化けする | `PYTHONUTF8=1` を付けて実行する |
| 認可で `403 access_denied`（アクセスをブロック） | 同意画面が「テスト」で、自分がテストユーザーに未登録。「対象」から追加する |
| `unauthorized_client`（401） | Refresh Token が、`.env` の Client ID/Secret とは別のクライアントで発行されている。Playground で **Use your own OAuth credentials** を有効にして取り直す |
| `invalid_grant` | Refresh Token が失効・無効。取り直す（「テスト」の間は 7 日で失効する） |

## セキュリティ注意

- **`.env` を Git にコミットしないこと**（`.gitignore` 済み）。`.env.example` にはキー名だけを書きます。
- Google Cloud からダウンロードする `client_secret_*.json` も、コミットしないこと（`.gitignore` 済み）。
- Client Secret / Refresh Token / Access Token はログに出力しません。
- `data/` には個人の健康データが入ります。`.gitignore` で除外済みで、リポジトリには含めません。
- 睡眠・歩数などの数値、スクリーンショット、ユーザー ID を含む JSON を、Issue や記事にそのまま貼らないでください。
