import os
import json
import yfinance as yf
import requests
from datetime import datetime
import pytz
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

BOT_TOKEN = os.environ.get("SOXL_TRADE_BOT")
CHAT_ID = os.environ.get("CHAT_ID")
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "balance": 7792.14,
        "holdings": 59,
        "avg_price": 61.79,
        "season2_profit": 1548.19,
        "season2_start": 10000.00,
        "updated_today": False
    }

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def get_soxl_data():
    try:
        soxl = yf.download("SOXL", period="2d", interval="30m", progress=False, auto_adjust=True)
        today = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
        today_data = soxl[soxl.index.strftime('%Y-%m-%d') == today]
        if len(today_data) == 0:
            today_data = soxl.tail(20)
        close_series = soxl['Close']
        volume_series = today_data['Volume']
        close_today = today_data['Close']
        vwap = float((close_today * volume_series).sum()) / float(volume_series.sum())
        close = float(close_series.iloc[-1])
        return round(vwap, 2), round(close, 2)
    except Exception as e:
        print(f"데이터 오류: {e}")
        return 55.0, 55.0

def calculate_plan(vwap, close, state):
    balance = state["balance"]
    holdings = state["holdings"]
    avg_price = state["avg_price"]

    budget = balance * 0.25
    buy1_price = round(vwap * 0.999, 2)
    buy2_price = round(vwap * 1.001, 2)
    buy1_qty = int((budget * 0.5) / buy1_price)
    buy2_qty = int((budget * 0.5) / buy2_price)

    sell_orders = []
    if close > avg_price * 1.01:
        sell_orders.append({"price": round(avg_price * 1.01, 2), "qty": int(holdings * 0.4), "type": "익절"})
        sell_orders.append({"price": round(avg_price * 1.015, 2), "qty": -1, "type": "익절"})
    elif close < avg_price * 0.98:
        sell_orders.append({"price": round(avg_price * 1.01, 2), "qty": int(holdings * 0.15), "type": "익절시도"})
        sell_orders.append({"price": round(vwap * 1.003, 2), "qty": int(holdings * 0.15), "type": "부분손절"})
        sell_orders.append({"price": round(vwap * 1.006, 2), "qty": int(holdings * 0.15), "type": "부분손절"})
    else:
        sell_orders.append({"price": round(avg_price * 1.005, 2), "qty": int(holdings * 0.3), "type": "익절"})
        sell_orders.append({"price": round(avg_price * 1.01, 2), "qty": -1, "type": "익절"})

    return buy1_price, buy1_qty, buy2_price, buy2_qty, sell_orders

def simulate_trade(vwap, close, state, buy1_price, buy1_qty, buy2_price, buy2_qty, sell_orders):
    balance = state["balance"]
    holdings = state["holdings"]
    avg_price = state["avg_price"]
    season2_profit = state["season2_profit"]
    realized = 0

    if buy1_price <= close * 1.01 and buy1_qty > 0:
        cost = buy1_price * buy1_qty
        if cost <= balance:
            avg_price = (avg_price * holdings + buy1_price * buy1_qty) / (holdings + buy1_qty)
            holdings += buy1_qty
            balance -= cost

    if buy2_price <= close * 1.01 and buy2_qty > 0:
        cost = buy2_price * buy2_qty
        if cost <= balance:
            avg_price = (avg_price * holdings + buy2_price * buy2_qty) / (holdings + buy2_qty)
            holdings += buy2_qty
            balance -= cost

    for order in sell_orders:
        sell_price = order["price"]
        sell_qty = order["qty"] if order["qty"] != -1 else holdings
        if sell_qty > 0 and holdings >= sell_qty:
            profit = (sell_price - avg_price) * sell_qty
            balance += sell_price * sell_qty
            realized += profit
            holdings -= sell_qty

    state["balance"] = round(balance, 2)
    state["holdings"] = holdings
    state["avg_price"] = round(avg_price, 3)
    state["season2_profit"] = round(season2_profit + realized, 2)
    state["updated_today"] = False
    return state

def build_message(state, vwap, close, buy1, qty1, buy2, qty2, sells, title="SOXL 매매 계획"):
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    profit_rate = round((state["season2_profit"] / state["season2_start"]) * 100, 2)
    unrealized = round((close - state["avg_price"]) * state["holdings"], 2)

    sell_msg = ""
    for o in sells:
        qty_txt = "나머지전부" if o["qty"] == -1 else str(o["qty"]) + "개"
        emoji = "🟢" if o["type"] == "익절" else "🟡"
        sell_msg += f"\n{emoji} ${o['price']} x {qty_txt} ({o['type']})"

    return (
        f"📊 {title} {now.strftime('%m/%d')}\n\n"
        f"[현재 상태]\n"
        f"잔금: ${state['balance']:,}\n"
        f"보유: {state['holdings']}개\n"
        f"평단: ${state['avg_price']}\n"
        f"전일종가: ${close}\n"
        f"평가손익: ${unrealized:+,}\n\n"
        f"VWAP: ${vwap}\n\n"
        f"[매수 계획]\n"
        f"${buy1} x {qty1}개\n"
        f"${buy2} x {qty2}개\n\n"
        f"[매도 계획]{sell_msg}\n\n"
        f"[수익 현황]\n"
        f"시즌2 실현수익: ${state['season2_profit']:,}\n"
        f"시즌2 수익률: {profit_rate}%"
    )

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

def morning_alert():
    print("아침 알림 실행!")
    state = load_state()
    vwap, close = get_soxl_data()
    buy1, qty1, buy2, qty2, sells = calculate_plan(vwap, close, state)
    msg = build_message(state, vwap, close, buy1, qty1, buy2, qty2, sells)
    send_telegram(msg)

def evening_check():
    print("저녁 체크 실행!")
    state = load_state()
    if not state.get("updated_today", False):
        vwap, close = get_soxl_data()
        buy1, qty1, buy2, qty2, sells = calculate_plan(vwap, close, state)
        new_state = simulate_trade(vwap, close, state, buy1, qty1, buy2, qty2, sells)
        save_state(new_state)
        send_telegram("⚙️ 오후 6시 자동 업데이트\n계획대로 체결 가정하여 내일 상태 반영했어요!")

@app.route(f"/webhook/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.json
    if "message" not in data:
        return "ok"
    text = data["message"].get("text", "")

    if text.startswith("업데이트"):
        try:
            state = load_state()
            parts = text.split()
            for part in parts:
                if "보유" in part:
                    state["holdings"] = int(part.replace("보유", ""))
                elif "평단" in part:
                    state["avg_price"] = float(part.replace("평단", ""))
                elif "잔금" in part:
                    state["balance"] = float(part.replace("잔금", ""))

            state["updated_today"] = True
            save_state(state)

            vwap, close = get_soxl_data()
            buy1, qty1, buy2, qty2, sells = calculate_plan(vwap, close, state)
            msg = build_message(state, vwap, close, buy1, qty1, buy2, qty2, sells, title="✅ 업데이트 완료! 내일 매매 계획")
            send_telegram(msg)

        except Exception as e:
            send_telegram(f"❌ 입력 오류: {str(e)}\n\n형식: 업데이트 보유59 평단61.41 잔금7792.14")

    return "ok"

@app.route("/")
def index():
    return "SOXL Bot Running!"

if __name__ == "__main__":
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(morning_alert, 'cron', day_of_week='mon-fri', hour=8, minute=0)
    scheduler.add_job(evening_check, 'cron', day_of_week='mon-fri', hour=18, minute=0)
    scheduler.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
```

**Commit changes → Render가 자동으로 재배포해요!**

2~3분 후 텔레그램에 다시 입력해보세요 😊
```
업데이트 보유59 평단61.79 잔금7792.14
