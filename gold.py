# -*- coding: utf-8 -*-
"""
上海黄金交易所 (SGE) Au99.99 行情抓取。

数据源: https://www.sge.com.cn/sjzx/quotation_daily_new?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
返回该交易日的 Au99.99 合约: 开盘/最高/最低/收盘/涨跌额/涨跌幅/加权均价 (元/克)。

SGE 的范围查询超过约 5 个交易日会只返回表头(已知缺陷), 因此按【单日】循环拉取。
策略:
  - 缓存缺失/不足时: 并发按单日循环补齐最近 3 个月(约 60 个交易日)。
  - 每次刷新: 若当天无数据则只拉取当天并追加。
"""
import os
import re
import json
import time
import logging
import datetime as dt
import concurrent.futures as cf
import threading
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "data", "gold.json")
HISTORY_DAYS = 92  # 回溯自然日数, 约 3 个月
SINGLE_WORKERS = 6  # 并发拉取 worker 数
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.sge.com.cn/",
}

log = logging.getLogger("gold")
_lock = threading.Lock()


def _num(s):
    """把 '983.56' / '-' / '1.59%' 之类的字符串转成 float, 失败返回 None。"""
    if s is None:
        return None
    s = s.strip().replace("%", "").replace(",", "")
    if s in ("", "-", "--", "—"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _strip_tags(x):
    return re.sub(r"<[^>]+>", "", x).strip()


def fetch_day(date_str):
    """拉取单个交易日的 Au99.99 行情。返回 dict 或 None(无行情/失败)。"""
    url = (
        "https://www.sge.com.cn/sjzx/quotation_daily_new"
        f"?start_date={date_str}&end_date={date_str}"
    )
    try:
        r = requests.get(url, headers=UA, timeout=15)
        r.raise_for_status()
    except Exception as e:
        log.warning("fetch %s failed: %s", date_str, e)
        return None
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S)
    for row in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(tds) < 8:
            continue
        cells = [_strip_tags(t) for t in tds]
        if cells[2] not in ("Au99.99", "AU9999"):
            continue
        return {
            "date": cells[1],
            "open": _num(cells[3]),
            "high": _num(cells[4]),
            "low": _num(cells[5]),
            "close": _num(cells[6]),
            "change": _num(cells[7]),      # 涨跌额(元)
            "change_pct": _num(cells[8]),  # 涨跌幅(%)
            "avg": _num(cells[9]) if len(cells) > 9 else None,
        }
    return None


def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.warning("cache corrupt, rebuilding")
    return {}


def _save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    os.replace(tmp, CACHE_FILE)


def _daterange_back(n_days):
    """返回今天往前 n_days 个自然日的 date 字符串列表(从新到旧)。"""
    today = dt.date.today()
    out = []
    for i in range(n_days):
        out.append((today - dt.timedelta(days=i)).isoformat())
    return out


def _ensure_history(cache):
    """若缓存中数据少于阈值(约 3 个月), 并发补齐最近 HISTORY_DAYS 自然日。"""
    existing = set(cache.keys())
    if len(existing) >= 40:  # 已有约 3 个月数据, 视为充足
        return cache
    # 需要补齐的日期 = 最近 HISTORY_DAYS 自然日中缓存里没有的
    need = [d for d in _daterange_back(HISTORY_DAYS) if d not in existing]
    if not need:
        return cache
    log.info("backfilling %d days of Au99.99 history", len(need))
    results = {}
    with cf.ThreadPoolExecutor(max_workers=SINGLE_WORKERS) as ex:
        for d, item in zip(need, ex.map(fetch_day, need)):
            if item and item.get("close") is not None:
                results[d] = item
    for d, item in results.items():
        cache[d] = item
    log.info("backfill added %d days", len(results))
    return cache


def _ensure_today(cache):
    """若今天无数据则拉取当天并追加。"""
    today = dt.date.today().isoformat()
    if today in cache and cache[today].get("close") is not None:
        return cache
    item = fetch_day(today)
    if item and item.get("close") is not None:
        cache[today] = item
        log.info("appended today %s close=%s", today, item["close"])
    return cache


def get_gold():
    """获取完整金价缓存(保证有 3 个月历史 + 今天)。带文件锁, 可并发调用。"""
    with _lock:
        cache = _load_cache()
        cache = _ensure_history(cache)
        cache = _ensure_today(cache)
        _save_cache(cache)
        return cache


def refresh_today():
    """仅尝试刷新今天的数据(用于每次页面刷新时调用)。"""
    with _lock:
        cache = _load_cache()
        cache = _ensure_today(cache)
        _save_cache(cache)
        return cache


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    t0 = time.time()
    data = get_gold()
    dates = sorted(data.keys())
    print(f"loaded {len(dates)} days in {time.time()-t0:.1f}s")
    if dates:
        print("range:", dates[0], "->", dates[-1])
        print("latest:", data[dates[-1]])
