# 気圧低下通知システム（BME680 × LINE Notify）

Raspberry Pi + InfluxDB + BME680 センサーで取得した気圧データを監視し、30分間で気圧が **1hPa以上下がった場合** に **LINEメッセージで警告**を送るシステムです。

## 特徴

* InfluxDBから30分前の気圧データを取得
* 最新の気圧データはAPIで取得
* 気圧差が -1.0 hPa 未満なら LINE通知
* 通知は **深夜0時〜6時** の間はスキップ
* 同一内容は **6時間に1回まで通知**
* `cron` による **10分ごとの定期実行**

---

## 環境

* Python 3.11
* Raspberry Pi または macOS/Linux
* InfluxDB 2.x
* LINE Notify API
* `.env` にて環境変数を管理

---

## セットアップ

### 1. `uv` による環境構築

```bash
# 仮想環境の作成
uv venv

# 仮想環境を有効化（macOS/Linux）
source .venv/bin/activate

# 依存パッケージのインストール
uv pip install -r requirements.txt
```

---

## 環境変数（`.env`）

以下のように `.env` ファイルをプロジェクトルートに配置してください：

```env
INFLUXDB_URL=http://localhost:YOURDB_PORT
INFLUXDB_TOKEN=your-token
INFLUXDB_ORG=your-org
INFLUXDB_BUCKET=your-bucket
LINE_NOTIFY_TOKEN=your-line-notify-token
```

---

## 定期実行設定（cron）

10分ごとにスクリプトを実行するには、以下のように `crontab` を編集します：

```bash
crontab -e
```

以下の行を追加（パスは適宜修正）：

```cron
*/10 * * * * cd /home/pi/pressure-alert && . .venv/bin/activate && python pressure_check.py >> logs/pressure.log 2>&1
```

### 説明：

* `*/10 * * * *`：10分ごとに実行
* `.venv/bin/activate`：仮想環境を有効化
* `>> logs/pressure.log 2>&1`：ログファイルに出力（標準出力＋標準エラー）

---

## ログファイル

スクリプトの実行ログは `notify.log` に記録されます。

ログフォルダが存在しない場合は、以下のコマンドで作成してください：

```bash
mkdir -p notify.log
```