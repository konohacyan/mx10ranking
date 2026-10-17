# -*- coding: utf-8 -*-
"""云端定时抓数：请求 mgtv 许愿池排名接口，更新 wish_records.csv
列头为 5 分钟对齐的时间戳（MMDDHHMM），同一槽位重复执行则覆盖。
同时增量生成 wish_growth.csv（相邻时间槽新增许愿数 = 增速），
已计算过的时间列直接跳过，避免重复计算。
"""
import csv
import json
import os
import urllib.request
import datetime

RANK_API = ("https://act.api.mgtv.com/api/v1/call/getRank"
            "?pid=1944&rank=50&showMyCAll=0&showInfo=1&startNum=0")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "wish_records.csv")
GROWTH_PATH = os.path.join(BASE_DIR, "wish_growth.csv")
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
CN_TZ = datetime.timezone(datetime.timedelta(hours=8))  # 北京时间


def fetch_rank():
    req = urllib.request.Request(RANK_API, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("errno") != 0:
        raise RuntimeError(f"接口返回异常: {data.get('msg')}")
    return [(item["rankName"], item["num"]) for item in data["data"]]


def slot_ts(now):
    now = now.astimezone(CN_TZ)  # GitHub Actions 服务器是 UTC，统一转北京时间
    minute = (now.minute // 5) * 5
    return now.replace(minute=minute, second=0, microsecond=0).strftime("%m%d%H%M")


def load_rows(path):
    """读取 csv 为二维表（首行表头），所有行补齐到同宽"""
    if not os.path.exists(path):
        return [["名字"]]
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return [["名字"]]
    width = max(len(r) for r in rows)
    return [r + [""] * (width - len(r)) for r in rows]


def save_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f).writerows(rows)


def upsert_col(rows, ts, values):
    """把 values={名字: 数值} 写入 rows 的 ts 列，列不存在则追加"""
    header = rows[0]
    if ts not in header:
        header.append(ts)
    col = header.index(ts)
    name_row = {r[0].strip(): i for i, r in enumerate(rows[1:], start=1) if r}
    for name, val in values.items():
        if name not in name_row:
            rows.append([name] + [""] * (len(header) - 1))
            name_row[name] = len(rows) - 1
        i = name_row[name]
        rows[i] += [""] * (len(header) - len(rows[i]))
        rows[i][col] = val


def append_to_csv(records, ts):
    rows = load_rows(CSV_PATH)
    upsert_col(rows, ts, dict(records))
    save_rows(CSV_PATH, rows)


def compute_diffs(rec_rows, skip_ts):
    """计算相邻时间列的差值（新增许愿数），skip_ts 中已有的列跳过"""
    header = rec_rows[0]
    result = {}  # ts -> {name: diff}
    for col in range(2, len(header)):
        # 最后一列始终重算：同一槽位被覆盖写入时保持与 records 一致
        if header[col] in skip_ts and col != len(header) - 1:
            continue
        diff = {row[0].strip(): str(int(row[col]) - int(row[col - 1]))
                for row in rec_rows[1:]
                if row[0].strip() and row[col].strip() and row[col - 1].strip()}
        if diff:
            result[header[col]] = diff
    return result


def update_growth():
    """增量补齐 wish_growth.csv：只计算尚未写入的时间列"""
    rec_rows = load_rows(CSV_PATH)
    growth_rows = load_rows(GROWTH_PATH)
    diffs = compute_diffs(rec_rows, set(growth_rows[0]))
    for ts, pairs in diffs.items():
        upsert_col(growth_rows, ts, pairs)
    if diffs:
        save_rows(GROWTH_PATH, growth_rows)
    return len(diffs)


def main():
    ts = slot_ts(datetime.datetime.now(datetime.timezone.utc))
    records = fetch_rank()
    append_to_csv(records, ts)
    added = update_growth()
    print(f"已写入列 {ts}（新增增速列 {added} 个）: "
          + ", ".join(f"{n}={v}" for n, v in records))


if __name__ == "__main__":
    main()
