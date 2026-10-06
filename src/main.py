"""sleep / steps / health metrics を順に取得して data/<今日(JST)>/ に保存する。

使い方: python src/main.py
1つの取得が失敗しても残りは続行し、1つでも失敗したら終了コード 1 で終わる（Actions で検知できる）。
"""

import sys

import fetch_health_metrics
import fetch_sleep
import fetch_steps
from auth import AuthError
from google_health_client import ApiError

TASKS = [
    ("sleep", fetch_sleep.main),
    ("steps", fetch_steps.main),
    ("health metrics", fetch_health_metrics.main),
]


def main() -> int:
    failed = []
    for name, task in TASKS:
        try:
            task()
        except (AuthError, ApiError) as e:
            print(f"ERROR ({name}): {e}", file=sys.stderr)
            failed.append(name)
        print()
    if failed:
        print(f"失敗: {', '.join(failed)}", file=sys.stderr)
        return 1
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
