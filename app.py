# -*- coding: utf-8 -*-
"""
Today —— 每日家人生日 + 上海金价 一屏看板。

- GET /            渲染前端页面(静态)
- GET /lunar.js    提供农历计算库(本地文件)
- GET /api/gold    金价数据(历史3个月+今天, 每次刷新刷新当天)
- GET /api/members 家人配置
"""
import os
import json
import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
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
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


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
