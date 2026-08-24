# -*- coding: utf-8 -*-
"""
Today —— 每日家人生日 + 上海金价 一屏看板。

- GET /            渲染前端页面(静态)
- GET /lunar.js    提供农历计算库(本地文件)
- GET /api/gold      金价数据(历史3个月+今天, 每次刷新刷新当天)
- GET /api/gold-live 当天实时金价(新浪 XAU 折算, 盘中实时, 10s 轮询)
- GET /api/members   家人配置
"""
import os
import json
import logging
import datetime as dt

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import gold

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("app")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = FastAPI(title="Today")

# 挂载静态目录 (style.css / app.js)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _load_members():
    with open(os.path.join(BASE_DIR, "members.json"), "r", encoding="utf-8") as f:
        return json.load(f)["members"]


@app.get("/", include_in_schema=False)
def index():
    # 给静态资源加内容 hash 版本号:
    # CDN/浏览器会缓存 css/js 很久, 部署新代码后旧缓存会导致页面行为过期。
    # 用文件 mtime 做版本号, 文件变了 URL 就变, 强制拉新资源。
    import time as _time

    def _ver(p):
        try:
            return str(int(os.path.getmtime(os.path.join(STATIC_DIR, p))))
        except OSError:
            return "0"

    v = ",".join(
        [
            _ver("app.js"),
            _ver("style.css"),
            _ver(os.path.join("..", "lunar.js")),
        ]
    )
    html = open(
        os.path.join(STATIC_DIR, "index.html"), "r", encoding="utf-8"
    ).read().replace("__STATIC_V__", v)
    return HTMLResponse(html)


@app.get("/lunar.js", include_in_schema=False)
def lunar_js():
    # 本地 UMD 文件, 浏览器里暴露全局 Solar / Lunar
    return FileResponse(
        os.path.join(BASE_DIR, "lunar.js"),
        media_type="application/javascript",
    )


@app.get("/api/gold")
def api_gold():
    """每次请求都会尝试刷新今天的数据, 并返回全部历史(滚动3个月)。"""
    try:
        cache = gold.refresh_today()
    except Exception as e:
        log.exception("refresh_today failed, falling back to full load")
        cache = gold.get_gold()
    # 按日期升序
    items = sorted(cache.values(), key=lambda x: x["date"])
    return JSONResponse(
        {
            "symbol": "Au99.99",
            "market": "上海黄金交易所 (SGE)",
            "unit": "元/克",
            "count": len(items),
            "data": items,
        }
    )


@app.get("/api/gold-live")
def api_gold_live():
    """当天实时金价(新浪现货黄金 XAU 折算元/克)。

    盘中 SGE 官网不发布当日数据, 此接口提供东方财富实时价;
    无数据(休市/抓取失败)时返回 source=fallback, 前端回退官方收盘。
    """
    live = gold.get_live()
    if live:
        return JSONResponse(live)
    # 回退: 用 SGE 官方最新一天(上一交易日)收盘价
    try:
        cache = gold.refresh_today()
        items = sorted(cache.values(), key=lambda x: x["date"])
        if items:
            last = items[-1]
            return JSONResponse(
                {
                    "date": last["date"],
                    "source": "fallback",
                    "price": last["close"],
                    "prev_close": items[-2]["close"] if len(items) > 1 else None,
                    "change": last.get("change"),
                    "change_pct": last.get("change_pct"),
                    "fetched_at": int(dt.datetime.now().timestamp()),
                }
            )
    except Exception as e:
        log.warning("gold-live fallback failed: %s", e)
    return JSONResponse({"source": "none"})


@app.get("/api/members")
def api_members():
    return JSONResponse(_load_members())


@app.on_event("startup")
def _warmup():
    # 启动时预热: 补齐3个月历史, 让首次访问快。失败不阻塞启动。
    def _run():
        try:
            gold.get_gold()
            log.info("warmup done, %d days cached", len(gold._load_cache()))
        except Exception as e:
            log.warning("warmup failed: %s", e)

    import threading
    threading.Thread(target=_run, daemon=True).start()
