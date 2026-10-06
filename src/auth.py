"""Refresh Token から Access Token を取得する。

環境変数は OS の環境変数を優先し、.env があれば補完する（GitHub Actions 対応）。
秘密情報はログに出さない。
"""

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://oauth2.googleapis.com/token"
REQUIRED_VARS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AuthError(Exception):
    pass


def load_credentials() -> dict[str, str]:
    # override=False: 既存の OS 環境変数は .env で上書きしない
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        raise AuthError(
            "必要な環境変数が未設定です: "
            + ", ".join(missing)
            + "（.env.example を .env にコピーして値を設定してください）"
        )
    return {name: os.environ[name] for name in REQUIRED_VARS}


def get_access_token() -> str:
    cred = load_credentials()
    try:
        resp = requests.post(
            TOKEN_URL,
            data={
                "client_id": cred["GOOGLE_CLIENT_ID"],
                "client_secret": cred["GOOGLE_CLIENT_SECRET"],
                "refresh_token": cred["GOOGLE_REFRESH_TOKEN"],
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise AuthError(f"Token endpoint への接続に失敗しました: {type(e).__name__}") from e

    if resp.status_code != 200:
        # 本文には error / error_description のみ含まれる（秘密情報は含まれない）
        raise AuthError(
            f"Access Token の取得に失敗しました: HTTP {resp.status_code} {resp.text}"
        )
    try:
        token = resp.json()["access_token"]
    except (ValueError, KeyError) as e:
        raise AuthError("Token レスポンスに access_token がありません") from e
    return token


if __name__ == "__main__":
    try:
        get_access_token()
    except AuthError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print("OK: access token を取得できました（値は表示しません）")
