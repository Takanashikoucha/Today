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
  因此盘中用新浪现货黄金 XAU(伦敦金)实时价 × 美元/人民币汇率 ÷ 7.824
  折算成元/克, 作为当天行情的实时估算值(标注"实时"), 收盘后官方
  日行情发布时自动以 SGE 官方收盘价为准。
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
XAU_CNY = 7.824  # 美元/人民币 近似汇率(XAU 美元/盎司 -> 元/克)
LIVE_TTL = 12  # 实时价缓存秒数(略大于前端 10s 轮询, 避免并发重复抓取)
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


# ---------------------------------------------------------------------------
# 实时价(盘中): 新浪现货黄金 XAU -> 元/克
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
    获取当天实时金价(元/克)。

    返回 dict 或 None:
      {
        "date": "YYYY-MM-DD",      # 当天
        "source": "live",           # 实时估算
        "provider": "新浪现货黄金 XAU × 汇率 7.824",
        "price": 983.56,            # 实时价(元/克)
        "prev_close": 968.14,       # 上一交易日 SGE 官方收盘
        "change": 15.42,            # price - prev_close (估算)
        "change_pct": 1.59,
        "updated_at": "14:49:00",   # 抓取时刻(本地)
        "xau": 4649.50,             # 原始 XAU 美元/盎司
      }

    带 LIVE_TTL 秒的文件缓存, 前端 10s 轮询时不会每个请求都打新浪。
    非交易日/休市时新浪无数据, 返回 None, 前端回退显示官方收盘。
    """
    today = today or dt.date.today().isoformat()
    with _lock:
        cached = _load_live()
        if cached and cached.get("date") == today:
            try:
                hms = cached["updated_at"].split(":")
                ts = dt.datetime.combine(
                    dt.date.today(),
                    dt.time(int(hms[0]), int(hms[1]), int(hms[2])),
                )
                if (dt.datetime.now() - ts).total_seconds() <= LIVE_TTL:
                    return cached
            except Exception:
                pass

        r = requests.get(
            "https://hq.sinajs.cn/list=hf_XAU",
            headers={
                "User-Agent": UA["User-Agent"],
                "Referer": "https://finance.sina.com.cn/",
            },
            timeout=8,
        )
        m = re.search(r'var hq_str_hf_XAU="([^"]*)"', r.text)
        if not m or not m.group(1):
            return None
        # 新浪 hf_XAU 实际字段(15个, 实测):
        #  0 最新价($) 1 买价($) 2 卖价($) 3 今日开($) 4 今日高($)
        #  5 今日低($) 6 更新时间 7 昨收($) 8 昨结算($) 9-11 0
        # 12 交易日期 13 名称
        f = m.group(1).split(",")
        xau = _num(f[0])
        if xau is None or xau <= 0:
            return None
        conv = XAU_CNY / 31.1035  # 美元/盎司 -> 元/克
        price = round(xau * conv, 2)
        prev_usd = _num(f[7])
        prev_close = round(prev_usd * conv, 2) if prev_usd else None
        chg = round(xau - prev_usd, 2) if prev_usd else None
        chg_pct = round(chg / prev_usd * 100, 2) if prev_usd and chg is not None else None
        item = {
            "date": today,
            "source": "live",
            "provider": "新浪现货黄金 XAU × 汇率 %.3f" % XAU_CNY,
            "price": price,
            "open": round(_num(f[3]) * conv, 2) if _num(f[3]) else None,
            "high": round(_num(f[4]) * conv, 2) if _num(f[4]) else None,
            "low": round(_num(f[5]) * conv, 2) if _num(f[5]) else None,
            "prev_close": prev_close,
            "change": chg,
            "change_pct": chg_pct,
            "updated_at": dt.datetime.now().strftime("%H:%M:%S"),
            "xau": xau,
        }
        _save_live(item)
        return item


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    t0 = time.time()
    data = get_gold()
    dates = sorted(data.keys())
    print(f"loaded {len(dates)} days in {time.time()-t0:.1f}s")
    if dates:
        print("range:", dates[0], "->", dates[-1])
        print("latest:", data[dates[-1]])
