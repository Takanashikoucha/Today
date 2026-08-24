# -*- coding: utf-8 -*-
"""
上海黄金交易所 (SGE) Au99.99 行情抓取。

数据源: https://www.sge.com.cn/sjzx/quotation_daily_new?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
返回该交易日的 Au99.99 合约: 开盘/最高/最低/收盘/涨跌额/涨跌幅/加权均价 (元/克)。

SGE 的范围查询超过约 5 个交易日会只返回表头(已知缺陷), 因此按【单日】循环拉取。
策略:
  - 缓存缺失/不足时: 并发按单日循环补齐最近 3 个月(约 60 个交易日)。
  - 每次刷新: 若当天无数据则只拉取当天并追加。

实时价(盘中):
  SGE 官网只在收盘后发布当日行情, 白天无法取到当天数据。
  因此盘中改用东方财富 SGE AU9999 实时行情接口
  (quote.eastmoney.com/globalfuture/AU9999.html 的数据源, secid=118.AU9999),
  提供当天最新的 SGE 合约价(元/克), 前端每 10 秒轮询; 休市/失败时
  回退显示 SGE 官方最新收盘价。
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
LIVE_FILE = os.path.join(BASE_DIR, "data", "gold_live.json")
HISTORY_DAYS = 92  # 回溯自然日数, 约 3 个月
SINGLE_WORKERS = 6  # 并发拉取 worker 数
LIVE_TTL = 8  # 实时价缓存秒数(小于前端 10s 轮询, 每次轮询基本都拿到新价)
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.sge.com.cn/",
}

log = logging.getLogger("gold")
_lock = threading.Lock()


def _num(s):
    """把 '983.56' / '-' / '1.59%' / 数字 之类的值转成 float, 失败返回 None。"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
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


# ---------------------------------------------------------------------------
# 实时价(盘中): 东方财富 SGE AU9999 实时行情(quote.eastmoney.com)
# ---------------------------------------------------------------------------
def _load_live():
    if os.path.exists(LIVE_FILE):
        try:
            with open(LIVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.warning("live cache corrupt, refetching")
    return None


def _save_live(item):
    os.makedirs(os.path.dirname(LIVE_FILE), exist_ok=True)
    tmp = LIVE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(item, f, ensure_ascii=False)
    os.replace(tmp, LIVE_FILE)


def get_live(today=None):
    """
    获取当天实时金价(元/克), 数据源: 东方财富 SGE AU9999 实时行情
    (即 https://quote.eastmoney.com/globalfuture/AU9999.html 页面的数据接口)。

    返回 dict 或 None:
      {
        "date": "YYYY-MM-DD",      # 当天
        "source": "live",           # 实时
        "provider": "东方财富 · 上海黄金交易所 Au9999",
        "price": 1004.3,            # 最新价(元/克)
        "open": 990.0,              # 今开
        "high": 1006.6,             # 最高
        "low": 985.0,               # 最低
        "prev_close": 983.56,       # 昨收
        "change": 20.74,            # 涨跌额
        "change_pct": 2.11,         # 涨跌幅(%)
        "fetched_at": 1753344000,   # 抓取时刻(UTC 时间戳, 前端按用户本地时区显示)
      }

    带 LIVE_TTL 秒的文件缓存, 前端 10s 轮询时不会每个请求都打接口。
    休市/无数据/抓取失败时返回 None, 前端回退显示 SGE 官方收盘。
    """
    today = today or dt.date.today().isoformat()
    with _lock:
        cached = _load_live()
        if cached and cached.get("date") == today:
            try:
                age = time.time() - float(cached.get("fetched_at", 0))
                if age <= LIVE_TTL:
                    return cached
            except Exception:
                pass

        # push2 主接口失败时回退 push2delay 延迟接口
        last_err = None
        for host in ("push2delay.eastmoney.com", "push2.eastmoney.com"):
            try:
                r = requests.get(
                    f"https://{host}/api/qt/stock/get",
                    params={
                        "secid": "118.AU9999",  # 118 = SGE(上海黄金交易所)
                        "fields": "f43,f44,f45,f46,f57,f58,f60,f169,f170,f171",
                        "invt": "2",
                        "fltt": "2",
                        "_": str(int(time.time() * 1000)),
                    },
                    headers={**UA, "Referer": "https://quote.eastmoney.com/"},
                    timeout=8,
                )
                r.raise_for_status()
                d = r.json().get("data")
                if not d:
                    return None
                # f43 最新价 f44 最高 f45 最低 f46 今开 f58 名称
                # f60 昨收 f169 涨跌额 f170 涨跌幅 f171 振幅
                price = _num(d.get("f43"))
                if price is None or price <= 0:
                    return None
                prev_close = _num(d.get("f60"))
                change = _num(d.get("f169"))
                change_pct = _num(d.get("f170"))
                if change is None and prev_close:
                    change = round(price - prev_close, 2)
                if change_pct is None and prev_close and change is not None:
                    change_pct = round(change / prev_close * 100, 2)
                item = {
                    "date": today,
                    "source": "live",
                    "provider": "东方财富 · 上海黄金交易所 Au9999",
                    "price": price,
                    "open": _num(d.get("f46")),
                    "high": _num(d.get("f44")),
                    "low": _num(d.get("f45")),
                    "prev_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    "fetched_at": int(time.time()),
                }
                _save_live(item)
                return item
            except Exception as e:
                last_err = e
                log.warning("eastmoney %s failed: %s", host, e)
        if last_err:
            log.warning("all eastmoney live sources failed: %s", last_err)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    t0 = time.time()
    data = get_gold()
    dates = sorted(data.keys())
    print(f"loaded {len(dates)} days in {time.time()-t0:.1f}s")
    if dates:
        print("range:", dates[0], "->", dates[-1])
        print("latest:", data[dates[-1]])
