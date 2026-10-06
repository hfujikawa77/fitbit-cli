"""Sleep データを取得して raw JSON を保存し、主要項目を表示する。

対象: 指定日(JST、省略時は今日)に終了した睡眠（= 今朝起きた前夜の睡眠）。
使い方: python src/fetch_sleep.py [YYYY-MM-DD]
"""

import sys
from datetime import datetime

from auth import get_access_token
from google_health_client import (
    TZ,
    get_data_points,
    jst_day_range_utc,
    run,
    save_json,
    today_jst,
)


def fetch(date: str, access_token: str) -> dict:
    start, end = jst_day_range_utc(date)
    return get_data_points(
        "sleep",
        access_token,
        params={"filter": f'sleep.interval.end_time >= "{start}" AND sleep.interval.end_time < "{end}"'},
    )


def _to_jst(rfc3339: str) -> str:
    return datetime.fromisoformat(rfc3339.replace("Z", "+00:00")).astimezone(TZ).strftime("%Y-%m-%d %H:%M")


def summarize(raw: dict) -> list[dict]:
    """実データ構造(dataPoints[].sleep.interval / summary.stagesSummary)に基づく抽出。
    想定外の形は例外にせずスキップする（raw JSON は保存済み）。
    """
    results = []
    for point in raw.get("dataPoints", []):
        sleep = point.get("sleep") or {}
        interval = sleep.get("interval") or {}
        summary = sleep.get("summary") or {}
        if "startTime" not in interval or "endTime" not in interval:
            continue
        stages = {s.get("type"): s.get("minutes") for s in summary.get("stagesSummary", [])}
        results.append(
            {
                "start": _to_jst(interval["startTime"]),
                "end": _to_jst(interval["endTime"]),
                "main_sleep": (sleep.get("metadata") or {}).get("mainSleep"),
                "minutes_in_sleep_period": summary.get("minutesInSleepPeriod"),
                "minutes_asleep": summary.get("minutesAsleep"),
                "awake_min": stages.get("AWAKE"),
                "light_min": stages.get("LIGHT"),
                "deep_min": stages.get("DEEP"),
                "rem_min": stages.get("REM"),
            }
        )
    return results


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else today_jst()
    print(f"Fetching sleep ({date} JST)...")
    raw = fetch(date, get_access_token())
    path = save_json(raw, "sleep", date)
    print(f"Saved: {path}")

    items = summarize(raw)
    if not items:
        print("該当する睡眠データはありません。")
    for it in items:
        print(
            f"  {it['start']} -> {it['end']} (main={it['main_sleep']}) "
            f"睡眠期間 {it['minutes_in_sleep_period']}分 / 実睡眠 {it['minutes_asleep']}分 | "
            f"Awake {it['awake_min']} Light {it['light_min']} Deep {it['deep_min']} REM {it['rem_min']} (分)"
        )


if __name__ == "__main__":
    run(main)
