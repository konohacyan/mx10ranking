# -*- coding: utf-8 -*-
"""云端定时抓数：请求 mgtv 许愿池排名接口，更新 wish_records.csv
列头为 5 分钟对齐的时间戳（MMDDHHMM），同一槽位重复执行则覆盖。
"""
import csv
import json
import os
import urllib.request
import datetime

RANK_API = ("https://act.api.mgtv.com/api/v1/call/getRank"
            "?pid=1944&rank=50&showMyCAll=0&showInfo=1&startNum=0")
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wish_records.csv")
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")


def fetch_rank():
    req = urllib.request.Request(RANK_API, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("errno") != 0:
        raise RuntimeError(f"接口返回异常: {data.get('msg')}")
    return [(item["rankName"], item["num"]) for item in data["data"]]


CN_TZ = datetime.timezone(datetime.timedelta(hours=8))  # 北京时间


def slot_ts(now):
    now = now.astimezone(CN_TZ)  # GitHub Actions 服务器是 UTC，统一转北京时间
    minute = (now.minute // 5) * 5
    return now.replace(minute=minute, second=0, microsecond=0).strftime("%m%d%H%M")


def append_to_csv(records, ts):
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    if not rows:
        rows = [["名字"]]

    header = rows[0]
    if ts in header:
        col = header.index(ts)
    else:
        header.append(ts)
        col = len(header) - 1

    name_row = {r[0].strip(): i for i, r in enumerate(rows[1:], start=1) if r}
    for name, num in records:
        i = name_row.get(name)
        if i is None:
            rows.append([name])
            i = len(rows) - 1
            name_row[name] = i
        rows[i] += [""] * (len(header) - len(rows[i]))
        rows[i][col] = num

    for row in rows:
        row += [""] * (len(header) - len(row))

    with open(CSV_PATH, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)


def main():
    ts = slot_ts(datetime.datetime.now(datetime.timezone.utc))
    records = fetch_rank()
    append_to_csv(records, ts)
    print(f"已写入列 {ts}: " + ", ".join(f"{n}={v}" for n, v in records))


if __name__ == "__main__":
    main()
