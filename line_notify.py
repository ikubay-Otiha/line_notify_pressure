import os
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from influxdb_client import InfluxDBClient

load_dotenv()

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
USER_IDS = os.getenv("LINE_USER_IDS").split(",")
URL = os.getenv("BME680_URL")

INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

LAST_NOTIFY_FILE = "last_notify.txt"  # 最終通知時刻を記録するファイル

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)


def get_bme680_data_from_influxdb() -> tuple:
    """InfluxDBから30分前の気圧データを取得する。

    Returns:
        tuple: JST時刻と気圧値 (datetime, float)
    """
    query = f'''
        from(bucket: "{INFLUX_BUCKET}")
        |> range(start: -31m, stop: -29m)
        |> filter(fn: (r) => r._measurement == "bme680" and r._field == "pressure")
        |> last()
    '''

    result = client.query_api().query(query)
    for table in result:
        for record in table.records:
            # Convert UTC time to JST
            time_utc = record.get_time()
            time_jst = time_utc.astimezone(timezone(timedelta(hours=9)))
            pressure = record.get_value()

            return time_jst, pressure


def analize_pressure_drop(
    current_jst_time, current_pressure, jst_time_30min_ago, pressure_30min_ago
):
    """現在と30分前の気圧を比較し、急激な気圧低下を検知・通知。

    Args:
        current_jst_time (datetime): 現在のJST時刻
        current_pressure (float): 現在の気圧
        jst_time_30min_ago (datetime): 30分前のJST時刻
        pressure_30min_ago (float): 30分前の気圧
    """
    if current_jst_time is None or current_pressure is None:
        print("Error: Current data is None")
        return False

    if jst_time_30min_ago is None or pressure_30min_ago is None:
        print("Error: Previous data is None")
        return False

    delta_pressure = current_pressure - pressure_30min_ago

    print(f"{jst_time_30min_ago} -> {current_jst_time}")
    print(f"気圧: {pressure_30min_ago} -> {current_pressure} hPa")
    print(f"差分: {delta_pressure} hPa")

    if is_night_hour(current_jst_time):
        print("夜間のため、通知をスキップします")
    elif delta_pressure < -1.0:
        if should_notify(current_jst_time):
            text = f"気圧が急激に下がっています。気圧:{current_pressure}hPa"
            send_message(text)
        else:
            print("6時間以内に通知済みのため、通知をスキップします")
    else:
        print("気圧に大きな変化はありません")


def send_message(msg_text: str):
    """指定されたメッセージをLINEに通知する。

    Args:
        msg_text (str): 通知するメッセージ本文
    """
    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json",
    }

    for uid in USER_IDS:
        uid = uid.strip()

        if uid:
            payload = {"to": uid, "messages": [{"type": "text", "text": msg_text}]}

            res = requests.post(
                "https://api.line.me/v2/bot/message/push", headers=headers, json=payload
            )
            print(f"Sent ro {uid}: {res.status_code} {res.text}")


def get_api_data() -> tuple:
    """外部APIから現在の気圧と時刻を取得。

    Raises:
        Exception: APIのステータスコードが200以外の場合

    Returns:
        tuple: JST時刻と気圧値 (datetime, float)
    """
    try:
        res = requests.get(URL)

        # APIのレスポンスが正常に動作しているか確認
        if res.status_code != 200:
            print(f"Error: {res.status_code}")
            raise Exception(f"Error: {res.status_code}")

        data = res.json()
        current_time_utc_str = data.get("timestamp")
        current_pressure = data.get("pressure")

        # ISO 8601文字列 → datetimeに変換（Python 3.7+）
        current_time_utc = datetime.fromisoformat(
            current_time_utc_str.replace("Z", "+00:00")
        )

        # JSTに変換
        current_time_jst = current_time_utc.astimezone(timezone(timedelta(hours=9)))

        return current_time_jst, current_pressure

    except Exception as e:
        print(f"Error: {e}")


def should_notify(current_jst_time: datetime, threshold: int = 360) -> bool:
    """最終通知時刻から指定時間が経過しているかどうかを確認。

    Args:
        current_jst_time (datetime): 現在時刻
        threshold (int): 通知間隔の閾値（分）

    Raises:
        ValueError: ファイルがない、または壊れている場合は通知する

    Returns:
        bool: 通知すべきかどうか
    """
    try:
        with open(LAST_NOTIFY_FILE, "r") as f:
            last_notify_time_str = f.read().strip()
            print(last_notify_time_str)
            print(type(last_notify_time_str))

            if not last_notify_time_str:
                raise ValueError("last_notify_time_str is empty")

            last_notify_time = datetime.fromisoformat(last_notify_time_str)
            if current_jst_time - last_notify_time < timedelta(minutes=threshold):
                return False

    except (FileNotFoundError, ValueError):
        pass  # ファイルがない、または壊れている場合は通知してよいとする

    with open(LAST_NOTIFY_FILE, "w") as f:
        f.write(current_jst_time.isoformat())

    return True


def is_night_hour(jst_time: datetime) -> bool:
    """夜間（日本時間0時〜6時）かどうかを判定。

    Args:
        jst_time (datetime): 現在のJST時刻

    Returns:
        bool: 夜間であればTrue
    """
    return 0 <= jst_time.hour < 6


if __name__ == "__main__":
    current_jst_time, current_pressure = get_api_data()
    jst_time_30min_ago, pressure_30min_ago = get_bme680_data_from_influxdb()

    analize_pressure_drop(
        current_jst_time, current_pressure, jst_time_30min_ago, pressure_30min_ago
    )
