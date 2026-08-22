# Today · 家人生日 & 上海金价

一屏看板：**月历**（农历/公历生日强调 + 每日金价涨跌红绿标记）→ **近三个月金价折线图** → **家人生日倒计时**。

部署目标：Render（免费层），启动时从外部实时拉取数据，依赖极轻、启动快。

## 功能

1. **月历视图**
   - 7×6 网格，显示公历日号 + 农历日。
   - 支持 上一年 / 上一月 / 今天 / 下一月 / 下一年 切换（方便查看未来生日）。
   - 生日强调：农历生日按当年公历落点标出（蓝色），公历生日固定标出（粉色），当日生日加 🎉 高亮。
   - 每个有行情的日子叠加金价涨跌：红 ▲ 涨 / 绿 ▼ 跌，并显示收盘价。
2. **金价（上海黄金交易所 Au99.99，元/克）**
   - 启动时并发补齐最近 **3 个月**历史（约 60+ 个交易日）。
   - **每次刷新页面**自动拉取当日最新数据并追加。
   - 缓存到 `data/gold.json`（Render 免费层休眠后文件丢失，冷启动会自动重建）。
3. **近三个月金价折线图**：纯 SVG 自绘，点按涨跌着色，悬停显示日期/收盘/涨跌。
4. **家人生日倒计时**：按距下个生日天数升序，今天标「🎂 今天」。

## 数据源

- **金价**：上海黄金交易所官网单日行情
  `https://www.sge.com.cn/sjzx/quotation_daily_new?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
  SGE 的范围查询超过 ~5 个交易日会只返回表头（已知缺陷），因此**按单日循环拉取**（6 并发，10 天约 0.4s）。
- **农历**：`lunar-javascript`（6tail，无第三方依赖，权威天文数据），打包成 `lunar.js` 由后端直接提供，**前端计算**，零后端农历依赖、零 CORS 问题。

## 目录

```
app.py            FastAPI：/ 页面、/lunar.js、/api/gold、/api/members
gold.py           SGE 抓取 + 3个月补齐 + 当日追加 + 文件缓存
lunar.js          农历库(浏览器全局 Solar/Lunar)
members.json      家人配置(可扩展)
static/           index.html / style.css / app.js
data/gold.json    金价缓存(运行时生成)
Procfile / runtime.txt / requirements.txt
```

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
# 打开 http://127.0.0.1:8000
```

## 新增家人 / 新生儿（重点）

只改 `members.json`，**无需改任何代码**：

```json
{ "name": "小名", "type": "lunar", "month": 8, "day": 1, "note": "" }
```

- `type`: `lunar` = 农历生日，`solar` = 公历(新历)生日
- `month` / `day`：对应历法下的月、日
- 数组里加一行即可，月历与倒计时自动适配。

## 部署到 Render

1. 新建 Web Service，连接本仓库。
2. Build Command 留空（Render 自动读 `requirements.txt`）；`runtime.txt` 指定 Python 3.12。
3. Start Command 已由 `Procfile` 指定：`uvicorn app:app --host 0.0.0.0 --port $PORT`。
4. 免费层会休眠，唤醒时冷启动会重新补齐 3 个月金价（并发约 2–3s），首次访问稍慢，之后正常。

> 说明：Render 免费层实例无持久磁盘，`data/gold.json` 每次冷启动都会重建，属预期行为；若需更快可升级付费 Starter 层（不休眠 + 持久磁盘）。
