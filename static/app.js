/* Today 前端: 月历 + 金价标记 + 折线图 + 生日倒计时 */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const pad2 = (n) => String(n).padStart(2, "0");
  const ymd = (y, m, d) => `${y}-${pad2(m)}-${pad2(d)}`;

  // 公历 -> 农历
  function lunarOf(y, m, d) {
    try {
      const l = Solar.fromYmd(y, m, d).getLunar();
      const isLeap = typeof l.isLeap === "function" ? l.isLeap() : !!l.isLeap;
      return {
        month: l.getMonth(),
        date: l.getDay(),
        leap: isLeap,
        str: l.getMonthInChinese() + "月" + l.getDayInChinese(),
      };
    } catch (e) {
      return null;
    }
  }
  // 农历年月日 -> 公历
  function lunarToSolar(lunarYear, lm, ld) {
    try {
      const l = Lunar.fromYmd(lunarYear, lm, ld);
      const s = l.getSolar();
      return { y: s.getYear(), m: s.getMonth(), d: s.getDay() };
    } catch (e) {
      return null;
    }
  }
  function diffDays(fromYmd, toYmd) {
    const [fy, fm, fd] = fromYmd.split("-").map(Number);
    const [ty, tm, td] = toYmd.split("-").map(Number);
    return Math.round((new Date(ty, tm - 1, td) - new Date(fy, fm - 1, fd)) / 86400000);
  }
  // 某成员的下一次生日(公历 ymd), 返回 {date} 或 null
  function nextBirthday(mem, today) {
    if (mem.type === "solar") {
      const y = today.y;
      let cand = ymd(y, mem.month, mem.day);
      if (cand < today.str) cand = ymd(y + 1, mem.month, mem.day);
      return { date: cand };
    }
    // lunar: 从当前公历年起找下一次落点
    for (let ly = today.y; ly <= today.y + 2; ly++) {
      const s = lunarToSolar(ly, mem.month, mem.day);
      if (!s) continue;
      const cand = ymd(s.y, s.m, s.d);
      if (cand >= today.str) return { date: cand };
    }
    return null;
  }

  // ---------- 状态 ----------
  const now = new Date();
  const today = { y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() };
  today.str = ymd(today.y, today.m, today.d);
  let viewY = today.y, viewM = today.m;
  let members = [];
  let gold = {}; // date -> {close, change, change_pct}
  let goldArr = []; // 升序

  // ---------- 顶栏 ----------
  function renderTopbar() {
    const wd = "日一二三四五六"[now.getDay()];
    $("topbar-date").textContent =
      `${today.y} 年 ${today.m} 月 ${today.d} 日 · 周${wd}`;
    const l = lunarOf(today.y, today.m, today.d);
    if (l) {
      const zodiac = (() => {
        try {
          return Solar.fromYmd(today.y, today.m, today.d)
            .getLunar()
            .getYearInGanZhi() + "年";
        } catch (e) {
          return "";
        }
      })();
      $("topbar-lunar").textContent = `农历 ${l.str}${l.leap ? "(闰)" : ""} · ${zodiac}`;
    }
  }

  // ---------- 月历 ----------
  function goldFor(dateStr) {
    return gold[dateStr] || null;
  }

  function buildBirthMap(y, m) {
    // 返回 { "yyyy-mm-dd": {names:[...], types:{}} }
    const map = {};
    members.forEach((mem) => {
      if (mem.type === "solar") {
        // 公历生日: 月份必须一致, 且该月存在这一天(如2月30则跳过)
        if (m !== mem.month) return;
        const dim = new Date(y, m, 0).getDate();
        if (mem.day > dim) return;
        const key = ymd(y, m, mem.day);
        map[key] = map[key] || { names: [], types: {} };
        map[key].names.push(mem.name);
        map[key].types["solar"] = 1;
      } else {
        // lunar: 找该公历月里, 农历月日 == mem 的日期
        const daysInMonth = new Date(y, m, 0).getDate();
        for (let d = 1; d <= daysInMonth; d++) {
          const l = lunarOf(y, m, d);
          if (l && l.month === mem.month && l.date === mem.day && !l.leap) {
            const key = ymd(y, m, d);
            map[key] = map[key] || { names: [], types: {} };
            map[key].names.push(mem.name);
            map[key].types["lunar"] = 1;
          }
        }
      }
    });
    return map;
  }

  function renderCalendar() {
    const title = $("cal-title");
    title.textContent = `${viewY} 年 ${viewM} 月`;
    const first = new Date(viewY, viewM - 1, 1);
    const startWeekday = first.getDay();
    const daysInMonth = new Date(viewY, viewM, 0).getDate();
    const bmap = buildBirthMap(viewY, viewM);
    const grid = $("cal-grid");
    grid.innerHTML = "";

    for (let i = 0; i < startWeekday; i++) {
      const c = document.createElement("div");
      c.className = "cell empty";
      grid.appendChild(c);
    }
    for (let d = 1; d <= daysInMonth; d++) {
      const key = ymd(viewY, viewM, d);
      const cell = document.createElement("div");
      cell.className = "cell" + (key === today.str ? " today" : "");

      const l = lunarOf(viewY, viewM, d);
      const dEl = document.createElement("div");
      dEl.className = "d";
      dEl.textContent = d;
      const lEl = document.createElement("div");
      lEl.className = "l";
      lEl.textContent = l ? l.str : "";
      cell.appendChild(dEl);
      cell.appendChild(lEl);

      // 生日
      const b = bmap[key];
      if (b) {
        const bd = document.createElement("div");
        let cls = "bday";
        if (b.types.lunar) cls += " has-b";
        if (b.types.solar) cls += " has-s";
        if (b.types.lunar && b.types.solar) cls += " both";
        bd.className = cls;
        if (key === today.str) {
          const cake = document.createElement("span");
          cake.className = "cake";
          cake.textContent = "🎉";
          cell.appendChild(cake);
        }
        b.names.forEach((n) => {
          const nm = document.createElement("span");
          nm.className = "nm";
          nm.textContent = n;
          bd.appendChild(nm);
        });
        cell.appendChild(bd);
      }

      // 金价 (优先于生日显示, 生日在上方)
      const g = goldFor(key);
      if (g && g.close != null) {
        const ge = document.createElement("div");
        const up = (g.change || 0) >= 0;
        ge.className = "gold " + (up ? "up" : "down");
        ge.innerHTML =
          `<span>${up ? "▲" : "▼"} ${up ? "+" : ""}${(g.change_pct != null ? g.change_pct : g.change)}</span><span class="p">${g.close}</span>`;
        cell.appendChild(ge);
      }
      grid.appendChild(cell);
    }
  }

  // ---------- 折线图 (SVG) ----------
  function renderChart() {
    const box = $("chart");
    box.innerHTML = "";
    const tip = $("chart-tip");
    if (!goldArr.length) {
      box.innerHTML = '<div class="loading">暂无金价数据</div>';
      return;
    }
    const W = 820, H = 300, P = { l: 52, r: 16, t: 16, b: 34 };
    const innerW = W - P.l - P.r, innerH = H - P.t - P.b;
    const closes = goldArr.map((g) => g.close).filter((v) => v != null);
    let min = Math.min(...closes), max = Math.max(...closes);
    if (min === max) { min -= 1; max += 1; }
    const pad = (max - min) * 0.08;
    min -= pad; max += pad;
    const n = goldArr.length;
    const x = (i) => P.l + (n === 1 ? innerW / 2 : (innerW * i) / (n - 1));
    const y = (v) => P.t + innerH - ((v - min) / (max - min)) * innerH;

    let svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
    // 网格 + y 轴刻度
    const ticks = 4;
    for (let i = 0; i <= ticks; i++) {
      const v = min + ((max - min) * i) / ticks;
      const yy = y(v);
      svg += `<line class="gridline" x1="${P.l}" y1="${yy}" x2="${W - P.r}" y2="${yy}"/>`;
      svg += `<text class="axis" x="${P.l - 6}" y="${yy + 3}" text-anchor="end">${v.toFixed(0)}</text>`;
    }
    // x 轴刻度(约5个)
    const step = Math.max(1, Math.floor(n / 5));
    for (let i = 0; i < n; i += step) {
      svg += `<text class="axis" x="${x(i)}" y="${H - 12}" text-anchor="middle">${goldArr[i].date.slice(5)}</text>`;
    }
    // 折线
    let path = "";
    goldArr.forEach((g, i) => {
      if (g.close == null) return;
      path += (path ? " L" : "M") + x(i) + " " + y(g.close);
    });
    svg += `<path d="${path}" fill="none" stroke="#f5b942" stroke-width="2" stroke-linejoin="round"/>`;
    // 数据点(按涨跌着色)
    goldArr.forEach((g, i) => {
      if (g.close == null) return;
      const up = (g.change || 0) >= 0;
      svg += `<circle class="${up ? "pt-up" : "pt-down"}" cx="${x(i)}" cy="${y(g.close)}" r="3.2"
        data-i="${i}" style="cursor:pointer"/>`;
    });
    svg += "</svg>";
    box.innerHTML = svg;

    // tooltip (真实浏览器里 svgEl 一定存在; 缺失时安全跳过)
    const svgEl = box.querySelector && box.querySelector("svg");
    if (svgEl) {
      svgEl.querySelectorAll("circle").forEach((c) => {
        c.addEventListener("mouseenter", (e) => {
          const i = +c.dataset.i;
          const g = goldArr[i];
          const up = (g.change || 0) >= 0;
          tip.hidden = false;
          tip.innerHTML =
            `<div><b>${g.date}</b></div>
             <div>收盘 ${g.close} 元/克</div>
             <div style="color:${up ? "#f0524d" : "#2fbf71"}">
               ${up ? "▲" : "▼"} ${up ? "+" : ""}${g.change} (${up ? "+" : ""}${g.change_pct}%)
             </div>`;
          const wrapRect = box.getBoundingClientRect();
          const cx = parseFloat(c.getAttribute("cx")) / W * wrapRect.width;
          const cy = parseFloat(c.getAttribute("cy")) / H * wrapRect.height;
          tip.style.left = Math.min(wrapRect.width - 130, cx + 10) + "px";
          tip.style.top = Math.max(0, cy - 50) + "px";
        });
        c.addEventListener("mouseleave", () => (tip.hidden = true));
      });
    }

    const first = goldArr[0].date, last = goldArr[goldArr.length - 1].date;
    $("gold-range").textContent = `${first} ~ ${last} · ${n} 个交易日`;
  }

  // ---------- 顶栏今日金价 ----------
  function renderGoldToday() {
    const el = goldArr[goldArr.length - 1];
    if (!el) { $("gt-price").textContent = "—"; return; }
    const up = (el.change || 0) >= 0;
    $("gt-price").textContent = el.close + " 元/克";
    const chg = $("gt-chg");
    chg.textContent = `${up ? "▲" : "▼"} ${up ? "+" : ""}${el.change} (${up ? "+" : ""}${el.change_pct}%)`;
    chg.style.color = up ? "var(--red)" : "var(--green)";
    const t = $("gt-time");
    if (t) t.textContent = `${el.date} 行情 · 更新于 ${new Date().toTimeString().slice(0, 8)}`;
  }

  // ---------- 每 10 秒自动刷新金价 ----------
  async function refreshGold() {
    try {
      const gRes = await fetch("/api/gold?_=" + Date.now(), { cache: "no-store" }).then((r) => r.json());
      const data = gRes.data || [];
      // 合并到本地缓存
      data.forEach((g) => (gold[g.date] = g));
      goldArr = data.slice().sort((a, b) => (a.date < b.date ? -1 : 1));
      renderGoldToday();
      renderChart();
      renderCalendar();
    } catch (e) {
      // 静默失败, 下次再试
      console.warn("gold refresh failed", e);
    }
  }

  // ---------- 倒计时 ----------
  function renderCountdown() {
    const list = $("cd-list");
    list.innerHTML = "";
    const rows = members.map((mem) => {
      const nb = nextBirthday(mem, today);
      if (!nb) return null;
      const days = diffDays(today.str, nb.date);
      return { mem, nb, days };
    }).filter(Boolean);
    rows.sort((a, b) => a.days - b.days);

    if (!rows.length) {
      list.innerHTML = '<div class="loading">暂无家人数据</div>';
      return;
    }
    rows.forEach((r) => {
      const { mem, nb, days } = r;
      const item = document.createElement("div");
      let cls = "cd-item";
      if (days === 0) cls += " is-today";
      else if (days <= 7) cls += " urgent";
      item.className = cls;

      const left = document.createElement("div");
      left.className = "cd-left";
      const name = document.createElement("div");
      name.className = "cd-name";
      name.textContent = (days === 0 ? "🎂 " : "") + mem.name;
      const meta = document.createElement("div");
      meta.className = "cd-meta";
      const tag = mem.type === "lunar" ? "农历" : "公历";
      const md = mem.month + "月" + mem.day + "日";
      meta.textContent = `${tag} ${md}`;
      left.appendChild(name);
      left.appendChild(meta);

      const right = document.createElement("div");
      right.className = "cd-num";
      const num = document.createElement("div");
      num.className = "cd-days" + (days === 0 ? " t" : days <= 7 ? " near" : "");
      num.textContent = days === 0 ? "今天" : days + " 天";
      const lbl = document.createElement("div");
      lbl.className = "cd-lbl";
      lbl.textContent = days === 0 ? "生日快乐" : "后 " + nb.date;
      right.appendChild(num);
      right.appendChild(lbl);

      item.appendChild(left);
      item.appendChild(right);
      list.appendChild(item);
    });
  }

  // ---------- 导航 ----------
  function shiftMonth(delta) {
    viewM += delta;
    if (viewM < 1) { viewM = 12; viewY--; }
    if (viewM > 12) { viewM = 1; viewY++; }
    renderCalendar();
  }
  function shiftYear(delta) {
    viewY += delta;
    renderCalendar();
  }

  function bindNav() {
    $("prev-month").onclick = () => shiftMonth(-1);
    $("next-month").onclick = () => shiftMonth(1);
    $("prev-year").onclick = () => shiftYear(-1);
    $("next-year").onclick = () => shiftYear(1);
    $("go-today").onclick = () => { viewY = today.y; viewM = today.m; renderCalendar(); };
  }

  // ---------- 初始化 ----------
  async function load() {
    renderTopbar();
    bindNav();
    renderCalendar(); // 先画月历骨架
    try {
      const [mRes, gRes] = await Promise.all([
        fetch("/api/members").then((r) => r.json()),
        fetch("/api/gold").then((r) => r.json()),
      ]);
      members = mRes;
      gold = {};
      (gRes.data || []).forEach((g) => (gold[g.date] = g));
      goldArr = (gRes.data || []).slice().sort((a, b) => (a.date < b.date ? -1 : 1));
      renderCalendar();
      renderChart();
      renderGoldToday();
      renderCountdown();
      // 启动 10 秒自动刷新
      setInterval(refreshGold, 10000);
    } catch (e) {
      console.error(e);
      $("cd-list").innerHTML = '<div class="loading">加载失败，请刷新重试</div>';
    }
  }

  load();
})();
