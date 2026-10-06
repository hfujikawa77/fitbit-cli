"""Steps データを取得して raw JSON を保存し、1日の総歩数を集計する。

対象: 指定日(JST、省略時は昨日)。歩数は前日分が確定値になるため、既定は昨日。
保存先: data/<実行日(JST)>/steps.json（日付を指定した場合は data/<指定日>/）
使い方: python src/fetch_steps.py [YYYY-MM-DD]
"""

import sys
from collections import defaultdict
from datetime import datetime, timedelta

from auth import get_access_token
from google_health_client import (
    TZ,
    get_all_data_points,
    jst_day_range_utc,
    post_daily_rollup,
    run,
    save_json,
    today_jst,
)


def default_target_date() -> str:
    return (datetime.now(TZ) - timedelta(days=1)).strftime("%Y-%m-%d")


def fetch(date: str, access_token: str) -> dict:
    start, end = jst_day_range_utc(date)
    return get_all_data_points(
        "steps",
        access_token,
        params={"filter": f'steps.interval.start_time >= "{start}" AND steps.interval.start_time < "{end}"'},
    )


def fetch_daily_rollup(date: str, access_token: str) -> dict:
    next_day = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    return post_daily_rollup("steps", access_token, date, next_day)


def rollup_total(rollup: dict) -> int | None:
    """dailyRollUp の rollupDataPoints[].steps.countSum（文字列）。"""
    for p in rollup.get("rollupDataPoints", []):
        try:
            return int(p["steps"]["countSum"])
        except (KeyError, TypeError, ValueError):
            continue
    return None


def summarize(raw: dict) -> dict[str, int]:
    """1分単位の生データ(dataPoints)を JST の日付ごとに単純合計する（ソース重複を含む）。
    civilStartTime.date ごとに count を合計。count は文字列なので int 化し、想定外の形はスキップ。
    """
    totals: dict[str, int] = defaultdict(int)
    for point in raw.get("dataPoints", []):
        steps = point.get("steps") or {}
        d = ((steps.get("interval") or {}).get("civilStartTime") or {}).get("date")
        try:
            key = f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}"
            totals[key] += int(steps["count"])
        except (TypeError, KeyError, ValueError):
            continue
    return dict(totals)


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else default_target_date()
    folder = sys.argv[1] if len(sys.argv) > 1 else today_jst()
    print(f"Fetching steps ({target} JST)...")
    token = get_access_token()
    raw = fetch(target, token)
    rollup = fetch_daily_rollup(target, token)
    path = save_json({"dataPoints": raw["dataPoints"], "dailyRollUp": rollup}, "steps", folder)
    print(f"Saved: {path} ({len(raw['dataPoints'])} points)")

    total = rollup_total(rollup)
    print(f"  {target}: {total if total is not None else '不明'} 歩 (dailyRollUp / 重複排除済み)")
    raw_total = sum(summarize(raw).values())
    if total is not None and raw_total != total:
        print(f"  参考: 生データ単純合計 {raw_total} 歩（複数ソースの重複を含む）")


if __name__ == "__main__":
    run(main)
