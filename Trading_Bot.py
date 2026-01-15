#下次修复：只能购买9999.99的问题

import asyncio
import yfinance as yf
import json
import os
import random
from playwright.async_api import async_playwright
from datetime import datetime

# 扩展代码：增加公司全称映射
COMPANY_NAMES = {
    "NVDA": "NVIDIA Corp", "TSLA": "Tesla, Inc", "AAPL": "Apple Inc", 
    "AMD": "AMD, Inc", "MSFT": "Microsoft", "GOOGL": "Alphabet Inc", 
    "AMZN": "Amazon.com", "META": "Meta Platforms", "NFLX": "Netflix", 
    "PLTR": "Palantir Tech", "BTC-USD": "Bitcoin", "MSTR": "MicroStrategy", "ETH-USD": "Ethereum"
}
TICKERS = list(COMPANY_NAMES.keys())
SAVE_FILE = "vanguard_v1.json"

class UltimateTerminal:
    def __init__(self):
        self.players = {
            "Human": {"cash": 10000.0, "holdings": {}, "history": [], "total_val": 10000.0, "cost_basis": {}},
            "Bot": {"cash": 10000.0, "holdings": {}, "history": [], "total_val": 10000.0, "cost_basis": {}}
        }
        self.load_game()
        self.current_ticker = TICKERS[0]
        self.market_data = {t: {"price": 0, "h_all": [], "dates": []} for t in TICKERS}

    def save_game(self):
        with open(SAVE_FILE, "w") as f:
            json.dump(self.players, f)

    def load_game(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, "r") as f:
                    self.players.update(json.load(f))
            except: pass

    async def fetch_data_task(self):
        while True:
            for ticker in TICKERS:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="2y") # 获取一个月数据计算趋势
                    if hist.empty: continue
                    
                    prices = [round(x, 2) for x in hist['Close'].tolist()]
                    dates = [d.strftime('%Y/%m/%d') for d in hist.index]
                    self.market_data[ticker].update({"price": prices[-1], "h_all": prices, "dates": dates})
                    
                    # --- 升级版：稳定爬坡 Bot 策略 ---
                    p = self.players["Bot"]
                    cur_price = prices[-1]
                    
                    # 计算简单的 5 日均线
                    if len(prices) >= 5:
                        ma5 = sum(prices[-5:]) / 5
                        
                        # 1. 买入逻辑：价格在均线上方（上升趋势）且现金充足
                        if cur_price > ma5 and p["cash"] > 500:
                            if random.random() < 0.15: # 提高触发概率
                                # 每次投入可用现金的 20%，让资产波动可见
                                buy_amt = p["cash"] * 0.2
                                qty = round(buy_amt / cur_price, 4)
                                await self.handle_trade("Bot", ticker, "buy", qty)
                        
                        # 2. 卖出逻辑：价格跌破均线（趋势反转）
                        elif cur_price < ma5 and p["holdings"].get(ticker, 0) > 0:
                            if random.random() < 0.3:
                                qty = p["holdings"][ticker]
                                await self.handle_trade("Bot", ticker, "sell", qty)
                                
                except Exception as e:
                    print(f"Update error: {e}")
                await asyncio.sleep(0.05)
            await asyncio.sleep(5)

    async def handle_trade(self, player, ticker, action, qty):
        try:
            qty = round(float(qty), 4)
            if qty <= 0: return {"status": "error", "msg": "INVALID QTY"}
            
            # 获取当前玩家对象
            p = self.players[player]
            price = self.market_data[ticker]["price"]
            
            if price == 0:
                return {"status": "error", "msg": "MARKET CLOSED"}
            
            cost = round(qty * price, 2)

            if action == "buy":
                if round(p["cash"], 2) < cost: 
                    return {"status": "error", "msg": "FUNDS DEPLETED"}
                
                old_qty = p["holdings"].get(ticker, 0)
                old_cost = p["cost_basis"].get(ticker, 0) * old_qty
                
                p["cash"] = round(p["cash"] - cost, 2) 
                p["holdings"][ticker] = round(old_qty + qty, 4)
                # 更新成本价
                p["cost_basis"][ticker] = round((old_cost + cost) / p["holdings"][ticker], 2)
                
                p['history'].append({
                    "time": datetime.now().strftime("%H:%M:%S"), 
                    "ticker": ticker, "act": "BUY", "qty": qty, 
                    "price": price, "total": cost
                })

            elif action == "sell":
                owned = p["holdings"].get(ticker, 0)
                # 允许极小的浮点数误差
                if owned < qty and abs(owned - qty) > 0.0001: 
                    return {"status": "error", "msg": "INSUFFICIENT ASSETS"}
                
                actual_qty = min(qty, owned)
                actual_revenue = round(actual_qty * price, 2) 
                
                p["cash"] = round(p["cash"] + actual_revenue, 2)
                p["holdings"][ticker] = round(owned - actual_qty, 4)
                
                if p["holdings"][ticker] <= 0.0001: 
                    p["holdings"][ticker] = 0
                    p["cost_basis"][ticker] = 0
                
                p['history'].append({
                    "time": datetime.now().strftime("%H:%M:%S"), 
                    "ticker": ticker, "act": "SELL", "qty": actual_qty, 
                    "price": price, "total": actual_revenue
                })
            
            self.save_game()
            return {"status": "success"}
        except Exception as e: 
            print(f"Trade Error: {e}")
            return {"status": "error", "msg": "SYS ERROR"}

    def get_ui_payload(self):
        for name in ["Human", "Bot"]:
            p = self.players[name]
            mv = sum(self.market_data[t]["price"] * q for t, q in p["holdings"].items() if t in self.market_data)
            p["total_val"] = round(p["cash"] + mv, 2)
        return json.dumps({"current": self.current_ticker, "market": self.market_data, "players": self.players, "names": COMPANY_NAMES})

    async def set_ticker(self, t):
        self.current_ticker = t
        return self.get_ui_payload()

    async def run(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.set_content(self.get_html_template())
            await page.expose_function("py_trade", self.handle_trade)
            await page.expose_function("py_set_ticker", self.set_ticker)
            asyncio.create_task(self.fetch_data_task())
            while True:
                try: 
                    payload = self.get_ui_payload()
                    await page.evaluate(f"updateUI({payload})")
                except: break
                await asyncio.sleep(1)

    def get_html_template(self):
        return """
        <style>
            :root { 
                --bg: #0b0f1a; --card: #151c2c; --primary: #38bdf8; --border: #2d3748;
                --text: #f1f5f9; --sub: #94a3b8; --green: #4ade80; --red: #fb7185;
            }
            * { box-sizing: border-box; font-family: 'Inter', sans-serif; outline: none; }
            body { background: var(--bg); color: var(--text); margin: 0; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }
            
            header { height: 60px; padding: 0 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; z-index: 10; background: var(--bg); }
            .stat-val { font-size: 18px; font-weight: 700; color: var(--primary); }

            .main-view { display: grid; grid-template-columns: 280px 1fr; flex: 1; overflow: hidden; position: relative; }
            
            .sidebar { border-right: 1px solid var(--border); display: flex; flex-direction: column; background: #080c14; height: 100%; overflow: hidden; }
            .sidebar-header { padding: 15px 20px; font-size: 11px; font-weight: 800; color: var(--sub); letter-spacing: 1px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
            #ticker-list { flex: 1; overflow-y: auto; padding-bottom: 20px; }
            .ticker-card { padding: 12px 20px; border-bottom: 1px solid var(--border); cursor: pointer; transition: 0.2s; }
            .ticker-card:hover { background: #111827; }
            .ticker-card.active { background: #1a2234; border-left: 4px solid var(--primary); }
            .ticker-name { font-size: 10px; color: var(--sub); margin-top: 2px; text-transform: uppercase; }

            .up { color: var(--green); } .down { color: var(--red); }

            .viewport { display: none; flex: 1; flex-direction: column; padding: 20px; overflow-y: auto; }
            .viewport-active { display: flex; }
            
            .chart-section { height: 400px; background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 15px; margin-bottom: 15px; position: relative; flex-shrink: 0; }
            
            .range-bar { display: flex; background: #1a2234; padding: 3px; border-radius: 6px; gap: 2px; }
            .range-btn { border: none; background: transparent; color: var(--sub); padding: 5px 10px; font-size: 11px; font-weight: 600; cursor: pointer; border-radius: 4px; }
            .range-btn.active { background: var(--primary); color: #000; }

            .action-area { display: flex; gap: 15px; margin-bottom: 20px; flex-shrink: 0; }
            .btn-trade { flex: 1; height: 50px; border: none; border-radius: 8px; font-weight: 700; cursor: pointer; font-size: 14px; }
            .buy { background: var(--green); color: #064e3b; }
            .sell { background: var(--red); color: #4c0519; }

            #modal { position: fixed; inset: 0; background: rgba(0,0,0,0.85); display: none; align-items: center; justify-content: center; z-index: 1000; }
            .modal-content { background: var(--card); width: 420px; border-radius: 16px; padding: 30px; border: 1px solid var(--border); box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
            .tab-bar { display: flex; background: #0b0f1a; border-radius: 8px; padding: 4px; margin-bottom: 20px; }
            .tab-item { flex: 1; text-align: center; padding: 8px; font-size: 12px; cursor: pointer; border-radius: 6px; color: var(--sub); font-weight: 600; }
            .tab-item.active { background: var(--primary); color: #000; }

            .input-box-wrapper { position: relative; margin-top: 10px; }
            input { width: 100%; background: #0b0f1a; border: 1px solid var(--border); color: white; padding: 15px; padding-right: 65px; border-radius: 8px; font-size: 20px; }
            .max-btn { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: var(--primary); color: black; border: none; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 800; cursor: pointer; }
            .max-btn:hover { filter: brightness(1.2); }
            
            .nav-container { height: 75px; display: flex; justify-content: center; align-items: center; border-top: 1px solid var(--border); flex-shrink: 0; background: var(--bg); }
            nav { width: 360px; height: 48px; background: var(--card); border-radius: 24px; border: 1px solid var(--border); display: flex; justify-content: space-around; align-items: center; }
            .nav-item { color: var(--sub); font-size: 12px; font-weight: 700; cursor: pointer; padding: 8px 18px; border-radius: 20px; }
            .nav-item.active { color: var(--primary); background: rgba(56,189,248,0.1); }
            
            /* 新增：Report 页面的分栏样式 */
            .report-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 10px; }
            .portfolio-header { padding: 10px; background: rgba(255,255,255,0.03); border-radius: 6px; font-size: 12px; font-weight: 700; color: var(--sub); margin-bottom: 10px; display: flex; justify-content: space-between; }
        </style>

        <header>
            <div style="font-weight: 800; font-size: 22px; letter-spacing: -1px;">VANGUARD<span style="color:var(--primary)">.CORE</span></div>
            <div style="display:flex; gap:40px;">
                <div style="text-align:right;"><div style="font-size:10px; color:var(--sub)">AVAIL CASH</div><div class="stat-val" id="h-cash">--</div></div>
                <div style="text-align:right;"><div style="font-size:10px; color:var(--sub)">NET ASSETS</div><div class="stat-val" id="h-total">--</div></div>
            </div>
        </header>

        <div class="main-view">
            <div class="sidebar">
                <div class="sidebar-header">MARKET WATCHLIST</div>
                <div id="ticker-list"></div>
            </div>
            
            <div id="p-market" class="viewport viewport-active">
                <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:20px;">
                    <div>
                        <h1 id="m-ticker" style="margin:0; font-size:36px; line-height:1;">--</h1>
                        <div id="m-full-name" style="color:var(--primary); font-size:14px; font-weight:600; margin-top:5px;">--</div>
                    </div>
                    <div class="range-bar">
                        <button class="range-btn" onclick="setRange(7, '7D')">7D</button>
                        <button class="range-btn active" onclick="setRange(30, '1M')">1M</button>
                        <button class="range-btn" onclick="setRange(90, '3M')">3M</button>
                        <button class="range-btn" onclick="setRange(180, '6M')">6M</button>
                        <button class="range-btn" onclick="setRange(365, '1Y')">1Y</button>
                        <button class="range-btn" onclick="setRange('YTD', 'YTD')">YTD</button>
                    </div>
                </div>
                <div class="chart-section"><canvas id="mainChart"></canvas></div>
                <div class="action-area">
                    <button onclick="openModal('buy')" class="btn-trade buy">BUY / LONG</button>
                    <button onclick="openModal('sell')" class="btn-trade sell">SELL / CLOSE</button>
                </div>
            </div>

            <div id="p-battle" class="viewport">
                <h3>BATTLE LOGS</h3>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
                    <div><h4 class="up">HUMAN_OPS</h4><div id="h-log"></div></div>
                    <div><h4 class="down">BOT_OPS</h4><div id="b-log"></div></div>
                </div>
            </div>

            <div id="p-report" class="viewport">
                <h3>PORTFOLIO PERFORMANCE</h3>
                <div class="report-grid">
                    <div>
                        <div class="portfolio-header"><span>HUMAN_PORTFOLIO</span><span id="r-h-total">--</span></div>
                        <div id="r-holdings-human"></div>
                    </div>
                    <div>
                        <div class="portfolio-header"><span>BOT_PORTFOLIO</span><span id="r-b-total">--</span></div>
                        <div id="r-holdings-bot"></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="nav-container">
            <nav id="bottom-nav">
                <div class="nav-item active" onclick="switchNav('market')">MARKET</div>
                <div class="nav-item" onclick="switchNav('battle')">BATTLE</div>
                <div class="nav-item" onclick="switchNav('report')">REPORT</div>
            </nav>
        </div>

        <div id="modal">
            <div class="modal-content">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                    <h2 id="modal-title" style="margin:0">TRADE</h2>
                    <div id="m-ticker-badge" style="background:var(--primary); color:black; padding:4px 8px; border-radius:4px; font-weight:800; font-size:12px;">--</div>
                </div>
                
                <div class="tab-bar">
                    <div class="tab-item active" id="tab-qty" onclick="setTradeMode('qty')">BY QUANTITY</div>
                    <div class="tab-item" id="tab-amt" onclick="setTradeMode('amt')">BY AMOUNT ($)</div>
                </div>

                <div style="background:rgba(0,0,0,0.2); padding:15px; border-radius:10px; border:1px solid var(--border); font-size:13px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span style="color:var(--sub)">Market Price</span><span id="m-unit-p" style="color:white; font-weight:700;">--</span>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span id="m-limit-label" style="color:var(--sub)">Available</span><span id="m-max-qty" style="color:var(--primary); font-weight:700;">--</span>
                    </div>
                </div>

                <div class="input-box-wrapper">
                    <input type="number" id="trade-input" placeholder="0.00" oninput="calcTrade()">
                    <button class="max-btn" onclick="applyMax()">MAX</button>
                </div>
                
                <div style="margin-top:20px; padding:15px; background:rgba(56,189,248,0.05); border-radius:10px; border:1px dashed var(--primary);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:12px; color:var(--sub);" id="res-label">Estimated Shares</span>
                        <span id="res-val" style="font-weight:800; color:var(--primary); font-size:18px;">0.00</span>
                    </div>
                </div>

                <div style="display:flex; justify-content:space-between; font-weight:800; font-size:24px; padding:20px 0;">
                    <span>TOTAL</span><span id="m-total">$0.00</span>
                </div>

                <div style="display:flex; gap:10px;">
                    <button onclick="closeModal()" style="flex:1; background:var(--border); color:white; border:none; border-radius:8px; cursor:pointer; font-weight:600;">CANCEL</button>
                    <button id="exec-btn" onclick="execute()" class="btn-trade buy" style="flex:2;">CONFIRM TRADE</button>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
            let chart; window.range = 30; window.lastData = null; window.curAct = 'buy'; window.tradeMode = 'qty';

            function init() {
                const ctx = document.getElementById('mainChart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: { labels: [], datasets: [{ data: [], borderColor: '#38bdf8', borderWidth: 2, pointRadius: 0, tension: 0.1, fill: true, backgroundColor: 'rgba(56,189,248,0.02)' }] },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        interaction: { mode: 'index', intersect: false },
                        scales: { 
                            x: { ticks: { font: { size: 10 }, color: '#475569' }, grid: { display: false } }, 
                            y: { grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: '#475569' } } 
                        },
                        plugins: { legend: { display: false } }
                    }
                });
            }

            function applyMax() {
                if (!window.lastData) return;
                const price = window.lastData.market[window.lastData.current].price;
                const h = window.lastData.players.Human;
                const owned = h.holdings[window.lastData.current] || 0;

                if (window.curAct === 'buy') {
                    if (window.tradeMode === 'qty') {
                        document.getElementById('trade-input').value = Math.floor((h.cash / price) * 10000) / 10000;
                    } else {
                        document.getElementById('trade-input').value = h.cash.toFixed(2);
                    }
                } else {
                    if (window.tradeMode === 'qty') {
                        document.getElementById('trade-input').value = owned;
                    } else {
                        document.getElementById('trade-input').value = Math.floor((owned * price) * 100) / 100;
                    }
                }
                calcTrade();
            }

            async function updateUI(data) {
                window.lastData = data;
                const h = data.players.Human; const b = data.players.Bot; const s = data.market[data.current];
                
                document.getElementById('h-cash').innerText = '$' + h.cash.toFixed(2);
                document.getElementById('h-total').innerText = '$' + h.total_val.toFixed(2);
                document.getElementById('r-h-total').innerText = 'NET: $' + h.total_val.toFixed(2);
                document.getElementById('r-b-total').innerText = 'NET: $' + b.total_val.toFixed(2);

                document.getElementById('ticker-list').innerHTML = Object.keys(data.market).map(t => {
                    const item = data.market[t]; if(!item.h_all.length) return '';
                    let r = window.range === 'YTD' ? (item.dates.length - item.dates.indexOf(item.dates.find(d => d.includes('/01/01')))) : window.range;
                    const startP = item.h_all[Math.max(0, item.h_all.length - (r||30))];
                    const diff = ((item.price - startP) / startP * 100).toFixed(2);
                    return `<div class="ticker-card ${t==data.current?'active':''}" onclick="py_set_ticker('${t}')">
                        <div style="display:flex; justify-content:space-between; font-weight:700;">
                            <span>${t}</span><span class="${diff>=0?'up':'down'}">${diff}%</span>
                        </div>
                        <div class="ticker-name">${data.names[t] || ''}</div>
                        <div style="font-size:14px; margin-top:4px; font-weight:600;">$${item.price.toFixed(2)}</div>
                    </div>`;
                }).join('');

                document.getElementById('m-ticker').innerText = data.current;
                document.getElementById('m-full-name').innerText = data.names[data.current];
                
                if (s.h_all.length > 0) {
                    let rIdx;
                    if (window.range === 'YTD') {
                        // 计算今年 1 月 1 日至今的天数
                        const firstDayOfYear = s.dates.find(d => d.includes('/01/01') || d.includes('/01/02'));
                        rIdx = firstDayOfYear ? s.dates.length - s.dates.indexOf(firstDayOfYear) : 252;
                    } else {
                        // 这里的 window.range 对应你点击按钮时传进去的 7, 30, 90, 180, 365
                        rIdx = window.range;
                    }

                    // 关键点：从末尾向前截取对应的天数
                    const sliceIdx = Math.max(0, s.h_all.length - rIdx);
                    chart.data.labels = s.dates.slice(sliceIdx);
                    chart.data.datasets[0].data = s.h_all.slice(sliceIdx);
                    
                    // 颜色逻辑：根据所选区间的开头和结尾对比来变色
                    chart.data.datasets[0].borderColor = s.h_all[sliceIdx] < s.price ? '#4ade80' : '#fb7185';
                    chart.update('none');
                }

                const logFmt = l => `<div style="padding:8px; border-bottom:1px solid #1a2234; font-size:11px;">[${l.time}] ${l.act} ${l.qty} ${l.ticker} @ ${l.price} | $${l.total.toFixed(2)}</div>`;
                document.getElementById('h-log').innerHTML = h.history.slice(-10).reverse().map(logFmt).join('');
                document.getElementById('b-log').innerHTML = data.players.Bot.history.slice(-10).reverse().map(logFmt).join('');
                
                // 渲染持仓函数
                const renderHoldings = (playerObj) => {
                    return Object.keys(playerObj.holdings).filter(t => playerObj.holdings[t]>0).map(t => {
                        const curPrice = data.market[t].price;
                        const avgCost = playerObj.cost_basis[t] || 0;
                        const pnl = avgCost > 0 ? ((curPrice - avgCost) / avgCost * 100).toFixed(2) : "0.00";
                        return `<div style="padding:10px; border-bottom:1px solid #1a2234; display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <div style="font-weight:700; font-size:12px;">${t} <span style="font-weight:normal; color:var(--sub); font-size:11px;">${playerObj.holdings[t]} Units</span></div>
                                <div style="font-size:10px; color:var(--sub)">Avg: $${avgCost.toFixed(2)}</div>
                            </div>
                            <div style="text-align:right">
                                <div class="up" style="font-weight:700; font-size:12px;">$${(playerObj.holdings[t]*curPrice).toFixed(2)}</div>
                                <div class="${pnl>=0?'up':'down'}" style="font-size:10px">${pnl}%</div>
                            </div>
                        </div>`;
                    }).join('') || '<div style="padding:20px; text-align:center; color:var(--sub); font-size:12px;">NO POSITIONS</div>';
                };

                document.getElementById('r-holdings-human').innerHTML = renderHoldings(h);
                document.getElementById('r-holdings-bot').innerHTML = renderHoldings(b);
            }

            function setTradeMode(m) {
                window.tradeMode = m;
                document.getElementById('tab-qty').classList.toggle('active', m=='qty');
                document.getElementById('tab-amt').classList.toggle('active', m=='amt');
                document.getElementById('res-label').innerText = m=='qty' ? 'Estimated Total Cost' : 'Estimated Shares';
                document.getElementById('trade-input').value = '';
                calcTrade();
            }

            function openModal(act) {
                if(!window.lastData) return;
                window.curAct = act;
                document.getElementById('modal').style.display = 'flex';
                document.getElementById('m-ticker-badge').innerText = window.lastData.current;
                const price = window.lastData.market[window.lastData.current].price;
                document.getElementById('m-unit-p').innerText = '$' + price.toFixed(2);
                
                if(act == 'buy') {
                    document.getElementById('m-limit-label').innerText = 'Cash Avail';
                    document.getElementById('m-max-qty').innerText = '$' + window.lastData.players.Human.cash.toFixed(2);
                    document.getElementById('exec-btn').className = 'btn-trade buy';
                    document.getElementById('exec-btn').innerText = 'CONFIRM BUY';
                } else {
                    document.getElementById('m-limit-label').innerText = 'Owned';
                    document.getElementById('m-max-qty').innerText = window.lastData.players.Human.holdings[window.lastData.current] || 0;
                    document.getElementById('exec-btn').className = 'btn-trade sell';
                    document.getElementById('exec-btn').innerText = 'CONFIRM SELL';
                }
                setTradeMode('qty');
            }

            function calcTrade() {
                if(!window.lastData) return;
                const val = parseFloat(document.getElementById('trade-input').value) || 0;
                const price = window.lastData.market[window.lastData.current].price;
                let finalQty = 0; let finalTotal = 0;

                if(window.tradeMode == 'qty') {
                    finalQty = val;
                    finalTotal = Math.round(val * price * 100) / 100;
                    document.getElementById('res-val').innerText = '$' + finalTotal.toFixed(2);
                } else {
                    finalTotal = Math.floor(val * 100) / 100;
                    finalQty = price > 0 ? finalTotal / price : 0;
                    document.getElementById('res-val').innerText = finalQty.toFixed(4) + ' Units';
                }

                document.getElementById('m-total').innerText = '$' + finalTotal.toFixed(2);
                window.currentCalcQty = finalQty;
                
                const btn = document.getElementById('exec-btn');
                const isInvalid = window.curAct == 'buy' ? 
                    (finalTotal > window.lastData.players.Human.cash + 0.01) : 
                    (finalQty > (window.lastData.players.Human.holdings[window.lastData.current] || 0) + 0.0001);
                btn.disabled = isInvalid || val <= 0;
            }

            function closeModal() { document.getElementById('modal').style.display = 'none'; }
            
            async function execute() {
                const res = await py_trade('Human', window.lastData.current, window.curAct, window.currentCalcQty);
                if(res.status == 'success') {
                    closeModal();
                } else {
                    alert(res.msg);
                }
            }

            function setRange(n, label) {
                window.range = n;
                document.querySelectorAll('.range-btn').forEach(b => b.classList.toggle('active', b.innerText == label));
                if(window.lastData) updateUI(window.lastData);
            }

            function switchNav(v) {
                document.querySelectorAll('.viewport').forEach(el => el.classList.remove('viewport-active'));
                document.querySelectorAll('nav .nav-item').forEach(el => el.classList.remove('active'));
                document.getElementById('p-' + v).classList.add('viewport-active');
                event.currentTarget.classList.add('active');
            }

            init();
        </script>
        """

if __name__ == "__main__":
    app = UltimateTerminal()
    asyncio.run(app.run())