"""Google Health API の共通クライアント。"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from auth import get_access_token

BASE_URL = "https://health.googleapis.com/v4"
TZ = ZoneInfo("Asia/Tokyo")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class ApiError(Exception):
    def __init__(self, status_code: int, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


def today_jst() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def jst_day_range_utc(date: str) -> tuple[str, str]:
    """JST の date (YYYY-MM-DD) の 00:00〜翌 00:00 を RFC-3339 (UTC) で返す。"""
    start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=TZ)
    end = start + timedelta(days=1)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.astimezone(timezone.utc).strftime(fmt), end.astimezone(timezone.utc).strftime(fmt)


def get_data_points(data_type: str, access_token: str, params: dict | None = None) -> dict:
    """GET /users/me/dataTypes/{data_type}/dataPoints"""
    url = f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            params=params,
            timeout=30,
        )
    except requests.RequestException as e:
        raise ApiError(0, f"接続に失敗しました: {type(e).__name__}") from e

    if resp.status_code != 200:
        raise ApiError(resp.status_code, resp.text)
    try:
        return resp.json()
    except ValueError as e:
        raise ApiError(resp.status_code, f"JSON パースに失敗しました: {resp.text[:200]}") from e


def get_all_data_points(
    data_type: str, access_token: str, params: dict | None = None, max_pages: int = 100
) -> dict:
    """nextPageToken を辿って全ページを取得し、dataPoints を結合した dict を返す。"""
    params = dict(params or {})
    points: list = []
    for _ in range(max_pages):
        page = get_data_points(data_type, access_token, params)
        points.extend(page.get("dataPoints", []))
        token = page.get("nextPageToken")
        if not token:
            return {"dataPoints": points}
        params["pageToken"] = token
    raise ApiError(0, f"{data_type}: {max_pages} ページを超えたため中断しました")


def post_daily_rollup(data_type: str, access_token: str, start_date: str, end_date: str) -> dict:
    """POST /users/me/dataTypes/{data_type}/dataPoints:dailyRollUp

    start_date / end_date は JST の暦日 (YYYY-MM-DD)。range は civil datetime 形式
    ({"date": {...}, "time": {}}) で、end は含まれない（1日分なら翌日を指定）。
    """

    def civil(d: str) -> dict:
        dt = datetime.strptime(d, "%Y-%m-%d")
        return {"date": {"year": dt.year, "month": dt.month, "day": dt.day}, "time": {}}

    url = f"{BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:dailyRollUp"
    body = {"range": {"start": civil(start_date), "end": civil(end_date)}, "windowSizeDays": 1}
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            json=body,
            timeout=30,
        )
    except requests.RequestException as e:
        raise ApiError(0, f"接続に失敗しました: {type(e).__name__}") from e
    if resp.status_code != 200:
        raise ApiError(resp.status_code, resp.text)
    try:
        return resp.json()
    except ValueError as e:
        raise ApiError(resp.status_code, f"JSON パースに失敗しました: {resp.text[:200]}") from e


def save_json(data: dict, name: str, date: str | None = None) -> Path:
    """data/YYYY-MM-DD/{name}.json に UTF-8・インデント付きで保存（上書き）。"""
    out_dir = DATA_DIR / (date or today_jst())
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run(main) -> None:
    """共通のエラー終了処理。"""
    from auth import AuthError

    try:
        main()
    except (AuthError, ApiError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
