"""保存済みの data/<日付>/sleep.json から睡眠ステージのグラフ(HTML/SVG)を作る。

使い方: python src/plot_sleep.py [YYYY-MM-DD]   （省略時は今日。先に fetch_sleep.py で取得しておく）
出力: data/<日付>/sleep.html  （API は呼ばない）
"""

import json
import sys
from datetime import datetime, timedelta

from google_health_client import DATA_DIR, TZ, today_jst

# 上から下の順（Fitbit アプリと同じ並び）
STAGES = [("AWAKE", "Awake", "#e0714f"), ("REM", "REM", "#5aa9d6"), ("LIGHT", "Light", "#7f8fe0"), ("DEEP", "Deep", "#3b3fa8")]
ROW = {key: i for i, (key, _, _) in enumerate(STAGES)}


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ)


def build_svg(sleep: dict) -> tuple[str, str]:
    stages = [(s["type"], _t(s["startTime"]), _t(s["endTime"])) for s in sleep["stages"] if s["type"] in ROW]
    start, end = _t(sleep["interval"]["startTime"]), _t(sleep["interval"]["endTime"])
    total = (end - start).total_seconds()

    left, right, top, row_h, bottom = 64, 16, 16, 44, 36
    width, height = 860, top + row_h * len(STAGES) + bottom
    plot_w = width - left - right
    x = lambda dt: left + (dt - start).total_seconds() / total * plot_w

    out = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="睡眠ステージの推移" width="100%">']
    for key, label, _ in STAGES:
        y = top + ROW[key] * row_h
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{y + row_h}" y2="{y + row_h}" class="grid"/>')
        out.append(f'<text x="{left - 8}" y="{y + row_h / 2 + 4}" text-anchor="end" class="lbl">{label}</text>')
    # 時刻の目盛り（毎正時）
    t = start.replace(minute=0, second=0, microsecond=0)
    while t <= end:
        if t >= start:
            out.append(f'<text x="{x(t):.1f}" y="{height - 12}" text-anchor="middle" class="lbl">{t:%H:%M}</text>')
        t += timedelta(hours=1)
    for key, s, e in stages:
        y = top + ROW[key] * row_h + 6
        color = next(c for k, _, c in STAGES if k == key)
        out.append(
            f'<rect x="{x(s):.1f}" y="{y}" width="{max(x(e) - x(s), 1):.1f}" height="{row_h - 12}" rx="3" '
            f'fill="{color}"><title>{key} {s:%H:%M}-{e:%H:%M}</title></rect>'
        )
    out.append("</svg>")

    summary = {s["type"]: int(s["minutes"]) for s in sleep["summary"]["stagesSummary"]}
    legend = "".join(
        f'<li><span style="background:{c}"></span>{label} <b>{summary.get(key, 0)}</b> 分</li>' for key, label, c in STAGES
    )
    return "\n".join(out), legend


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else today_jst()
    src = DATA_DIR / date / "sleep.json"
    points = json.loads(src.read_text(encoding="utf-8")).get("dataPoints", [])
    mains = [p["sleep"] for p in points if (p["sleep"].get("metadata") or {}).get("mainSleep")] or [p["sleep"] for p in points]
    if not mains:
        sys.exit(f"ERROR: {src} に睡眠データがありません")
    sleep = mains[0]
    svg, legend = build_svg(sleep)
    s, e = _t(sleep["interval"]["startTime"]), _t(sleep["interval"]["endTime"])
    sm = sleep["summary"]

    html = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>睡眠 {date}</title>
<style>
:root{{--bg:#fff;--fg:#1f2330;--mute:#6b7080;--line:#e3e5ec}}
@media (prefers-color-scheme:dark){{:root{{--bg:#15171d;--fg:#e8eaf0;--mute:#9aa0b0;--line:#2c303b}}}}
body{{font-family:system-ui,"Yu Gothic UI",sans-serif;background:var(--bg);color:var(--fg);margin:0;padding:24px 16px}}
main{{max-width:900px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:var(--mute);margin:0 0 20px}}
.lbl{{fill:var(--mute);font-size:12px}} .grid{{stroke:var(--line);stroke-width:1}}
ul{{display:flex;flex-wrap:wrap;gap:8px 20px;list-style:none;padding:0;margin:16px 0}}
li span{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}}
.kv{{color:var(--mute)}} .kv b{{color:var(--fg)}}
</style></head><body><main>
<h1>{date} の睡眠</h1>
<p class="sub">{s:%H:%M} → {e:%H:%M}（JST）</p>
{svg}
<ul>{legend}</ul>
<p class="kv">睡眠期間 <b>{sm['minutesInSleepPeriod']}</b> 分 / 実睡眠 <b>{sm['minutesAsleep']}</b> 分 / 中途覚醒 <b>{sm['minutesAwake']}</b> 分</p>
</main></body></html>"""
    out = DATA_DIR / date / "sleep.html"
    out.write_text(html, encoding="utf-8")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
