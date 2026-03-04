import os
import yfinance as yf
import requests
from datetime import datetime
import pytz

BOT_TOKEN = os.environ.get("SOXL_TRADE_BOT")
CHAT_ID = os.environ.get("CHAT_ID")

잔금 = 7715.47
보유개수 = 59
평단 = 64.961
시즌2_실현수익 = 1548.19
시즌2_시작원금 = 10000.00

def get_soxl_data():
    soxl = yf.download("SOXL", period="2d", interval="30m", progress=False)
    today = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
    today_data = soxl[soxl.index.strftime('%Y-%m-%d') == today]
    if len(today_data) == 0:
        today_data = soxl.tail(20)
    vwap = float((today_data['Close'] * today_data['Volume']).sum() / today_data['Volume'].sum())
    종가 = float(soxl['Close'].iloc[-1])
    return round(vwap, 2), round(종가, 2)

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })
    print(f"전송결과: {response.status_code}")
    return response.status_code == 200

def main():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    vwap, 종가 = get_soxl_data()

    매수가1 = round(vwap * 0.999, 2)
    매수가2 = round(vwap * 1.001, 2)
    매수예산 = 잔금 * 0.25
    매수수량1 = int((매수예산 * 0.5) / 매수가1)
    매수수량2 = int((매수예산 * 0.5) / 매수가2)

    if 종가 > 평단 * 1.01:
        매도상황 = f"🟢 익절\n├ ${round(평단*1.01,2)} × {int(보유개수*0.4)}개\n└ ${round(평단*1.015,2)} × 나머지전부"
    elif 종가 < 평단 * 0.99:
        손절가 = round(vwap * 1.001, 2)
        손절수량 = int(보유개수 * 0.2)
        매도상황 = f"🟡 부분손절\n└ ${손절가} × {손절수량}개"
    else:
        매도상황 = "⏸ 매도 조건 미충족 (보유 유지)"

    수익률 = round((시즌2_실현수익 / 시즌2_시작원금) * 100, 2)
    평가손익 = round((종가 - 평단) * 보유개수, 2)

    msg = f"""📊 <b>SOXL 매매 계획 {now.strftime('%m/%d')}</b>

💰 <b>현재 상태</b>
├ 잔금: ${잔금:,.2f}
├ 보유: {보유개수}개
├ 평단: ${평단}
├ 전일종가: ${종가}
└ 평가손익: ${평가손익:+,.
