"""健康指標を取得して data/<実行日(JST)>/health_metrics.json に raw JSON を保存する。

指標を増やすときは METRICS に1行追加する（dataType 名は公式ドキュメントで確認済みのもののみ）。
  公式: https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints

window の意味（JST）:
  recent    昨日と今日の2日分。日次サマリ型は起床した日（今日）の日付で入るが、
            SpO2 など前日付けで入るものもあるため、2日分を取って取りこぼしを防ぐ。
  yesterday 昨日1日分（steps と同じ）。
  last30d   直近30日（体重のように毎日は記録されないもの）。

使い方: python src/fetch_health_metrics.py
"""

from datetime import datetime, timedelta

from auth import get_access_token
from google_health_client import (
    TZ,
    ApiError,
    get_all_data_points,
    post_daily_rollup,
    run,
    save_json,
    today_jst,
)

# name: 出力キー / data_type: URL の kebab-case / filter_field: フィルタ用 snake_case のフィールド
# kind: "date"(日次サマリ, ISO日付) | "civil"(サンプル, civil_time) | "rollup"(dailyRollUp で日次集計)
# 心拍は1日 3万件超(約26MB)になるため raw ではなく dailyRollUp(平均/最小/最大)を保存する。
METRICS = [
    {"name": "heart_rate", "data_type": "heart-rate", "kind": "rollup", "window": "yesterday"},
    {"name": "resting_heart_rate", "data_type": "daily-resting-heart-rate",
     "filter_field": "daily_resting_heart_rate.date", "kind": "date", "window": "recent"},
    {"name": "spo2", "data_type": "daily-oxygen-saturation",
     "filter_field": "daily_oxygen_saturation.date", "kind": "date", "window": "recent"},
    {"name": "hrv", "data_type": "daily-heart-rate-variability",
     "filter_field": "daily_heart_rate_variability.date", "kind": "date", "window": "recent"},
    {"name": "respiratory_rate", "data_type": "daily-respiratory-rate",
     "filter_field": "daily_respiratory_rate.date", "kind": "date", "window": "recent"},
    {"name": "weight", "data_type": "weight", "filter_field": "weight.sample_time.civil_time",
     "kind": "civil", "window": "last30d"},
]


def _days(window: str) -> tuple[str, str]:
    """window -> (開始日, 終了日(含まない)) の JST 暦日。"""
    today = datetime.now(TZ).date()
    if window == "recent":
        start, end = today - timedelta(days=1), today + timedelta(days=1)
    elif window == "yesterday":
        start, end = today - timedelta(days=1), today
    elif window == "last30d":
        start, end = today - timedelta(days=30), today + timedelta(days=1)
    else:
        raise ValueError(f"unknown window: {window}")
    return start.isoformat(), end.isoformat()


def build_filter(metric: dict) -> str:
    start, end = _days(metric["window"])
    field = metric["filter_field"]
    return f'{field} >= "{start}" AND {field} < "{end}"'


def fetch_metric(metric: dict, access_token: str) -> dict:
    if metric["kind"] == "rollup":
        start, end = _days(metric["window"])
        rollup = post_daily_rollup(metric["data_type"], access_token, start, end)
        return {"dataPoints": rollup.get("rollupDataPoints", [])}
    return get_all_data_points(
        metric["data_type"],
        access_token,
        params={"filter": build_filter(metric), "pageSize": 10000},
    )


def describe(name: str, points: list) -> str:
    """実データ構造(各 dataPoint 直下のキー)に基づく1行要約。未知の形は件数のみ。"""
    if not points:
        return "データなし"
    try:
        if name == "heart_rate":
            return ", ".join(
                f"{_d(p['civilStartTime']['date'])}: min {p['heartRate']['beatsPerMinuteMin']} / "
                f"avg {p['heartRate']['beatsPerMinuteAvg']:.0f} / max {p['heartRate']['beatsPerMinuteMax']} bpm"
                for p in points
            )
        if name == "resting_heart_rate":
            return ", ".join(
                f"{_d(p['dailyRestingHeartRate']['date'])}: {p['dailyRestingHeartRate']['beatsPerMinute']} bpm"
                for p in points
            )
        if name == "spo2":
            return ", ".join(
                f"{_d(p['dailyOxygenSaturation']['date'])}: avg {p['dailyOxygenSaturation']['averagePercentage']}%"
                for p in points
            )
        if name == "hrv":
            return ", ".join(
                f"{_d(p['dailyHeartRateVariability']['date'])}: "
                f"{p['dailyHeartRateVariability']['averageHeartRateVariabilityMilliseconds']} ms"
                for p in points
            )
        if name == "respiratory_rate":
            return ", ".join(
                f"{_d(p['dailyRespiratoryRate']['date'])}: {p['dailyRespiratoryRate']['breathsPerMinute']} 回/分"
                for p in points
            )
    except (KeyError, TypeError, ValueError):
        pass
    return f"{len(points)}件（構造未解析・raw を参照）"


def _d(date: dict) -> str:
    return f"{date['year']:04d}-{date['month']:02d}-{date['day']:02d}"


def main() -> None:
    print("Fetching health metrics...")
    token = get_access_token()
    result: dict = {}
    for metric in METRICS:
        name = metric["name"]
        try:
            raw = fetch_metric(metric, token)
        except ApiError as e:
            # 1指標の失敗で全体を止めない。エラー内容は JSON にも残す。
            result[name] = {"dataType": metric["data_type"], "error": {"status": e.status_code, "body": e.body}}
            print(f"  {name}: ERROR HTTP {e.status_code}")
            continue
        result[name] = {"dataType": metric["data_type"], "dataPoints": raw["dataPoints"]}
        print(f"  {name}: {describe(name, raw['dataPoints'])}")

    path = save_json(result, "health_metrics", today_jst())
    print(f"Saved: {path}")


if __name__ == "__main__":
    run(main)
