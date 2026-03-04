import os
import yfinance as yf
import requests
from datetime import datetime
import pytz

BOT_TOKEN = os.environ.get("8705583279:AAGk6V3YyGWz2LrLcSXL5P0uHu9dKBmyk5s")
CHAT_ID = os.environ.get("8742209830")

balance = 7715.47
holdings = 59
avg_price = 64.961
season2_profit = 1548.19
season2_start = 10000.00

def get_soxl_data():
    soxl = yf.download("SOXL", period="2d", interval="30m", progress=False)
    today = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
    today_data = soxl[soxl.index.strftime('%Y-%m-%d') == today]
    if len(today_data) == 0:
        today_data = soxl.tail(20)
    vwap = float((today_data['Close'] * today_data['Volume']).sum() / today_data['Volume'].sum())
    close = float(soxl['Close'].iloc[-1])
    return round(vwap, 2), round(close, 2)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    print(f"Status: {response.status_code}")

def main():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    vwap, close = get_soxl_data()

    buy1 = round(vwap * 0.999, 2)
    buy2 = round(vwap * 1.001, 2)
    budget = balance * 0.25
    qty1 = int((budget * 0.5) / buy1)
    qty2 = int((budget * 0.5) / buy2)

    if close > avg_price * 1.01:
        sell_plan = "PROFIT: $" + str(round(avg_price*1.01,2)) + " x " + str(int(holdings*0.4)) + " / $" + str(round(avg_price*1.015,2)) + " x rest"
    elif close < avg_price * 0.99:
        stop_price = round(vwap * 1.001, 2)
        stop_qty = int(holdings * 0.2)
        sell_plan = "PARTIAL STOP: $" + str(stop_price) + " x " + str(stop_qty)
    else:
        sell_plan = "HOLD - no sell condition"

    profit_rate = round((season2_profit / season2_start) * 100, 2)
    unrealized = round((close - avg_price) * holdings, 2)

    msg = (
        "SOXL Trade Plan " + now.strftime('%m/%d') + "\n\n"
        "Balance: $" + str(balance) + "\n"
        "Holdings: " + str(holdings) + " shares\n"
        "Avg Price: $" + str(avg_price) + "\n"
        "Last Close: $" + str(close) + "\n"
        "Unrealized: $" + str(unrealized) + "\n\n"
        "VWAP: $" + str(vwap) + "\n\n"
        "BUY PLAN\n"
        "$" + str(buy1) + " x " + str(qty1) + "\n"
        "$" + str(buy2) + " x " + str(qty2) + "\n\n"
        "SELL PLAN\n"
        + sell_plan + "\n\n"
        "Season2 Profit: $" + str(season2_profit) + "\n"
        "Season2 Return: " + str(profit_rate) + "%"
    )

    send_telegram(msg)
    print(msg)

main()
