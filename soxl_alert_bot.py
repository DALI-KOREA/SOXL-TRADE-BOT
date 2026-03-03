
# ================================================================
# SOXL VWAP 매매 알림 봇
# 익절 + 부분손절 (원본방식)
# 매일 한국시간 오전 8시 자동실행 (GitHub Actions)
# ================================================================

!pip install yfinance -q

import yfinance as yf
import requests
from datetime import datetime
import pytz

# ================================================================
# ⬇️ 여기만 매일 업데이트 하세요!
# ================================================================
BOT_TOKEN = "여기에_텔레그램_토큰_입력"
CHAT_ID = "8742209830"

# 오늘 현재 상태 (매매 후 업데이트)
잔금 = 7715.47        # 현재 잔금 $
보유개수 = 59          # 현재 보유 주식 수
평단 = 64.961         # 현재 평균 단가
시즌2_실현수익 = 1548.19  # 시즌2 누적 실현수익 $
시즌2_시작원금 = 10000.00  # 시즌2 시작원금
현사이클_시작금 = 11559.35  # 현재 사이클 시작금
# ================================================================

def get_soxl_data():
    """SOXL 데이터 가져오기"""
    soxl = yf.download("SOXL", period="2d", interval="30m", progress=False)
    
    # 오늘 데이터만
    today = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
    today_data = soxl[soxl.index.strftime('%Y-%m-%d') == today]
    
    if len(today_data) == 0:
        # 장 시작 전이면 전날 데이터로 VWAP 계산
        today_data = soxl.tail(20)
    
    # VWAP 계산
    vwap = float((today_data['Close'] * today_data['Volume']).sum() / today_data['Volume'].sum())
    종가 = float(soxl['Close'].iloc[-1])
    
    return round(vwap, 2), round(종가, 2)

def calculate_buy_plan(vwap, 잔금, 보유개수, 평단):
    """매수 계획 계산"""
    # 잔금의 약 25% 사용 (원본처럼 현금 항상 보유)
    매수예산 = 잔금 * 0.25
    
    # 2개 가격대로 분할 매수 (VWAP 기준 위아래)
    매수가1 = round(vwap * 0.999, 2)   # VWAP보다 약간 낮게
    매수가2 = round(vwap * 1.001, 2)   # VWAP보다 약간 높게
    
    매수수량1 = int((매수예산 * 0.5) / 매수가1)
    매수수량2 = int((매수예산 * 0.5) / 매수가2)
    
    return 매수가1, 매수수량1, 매수가2, 매수수량2

def calculate_sell_plan(vwap, 보유개수, 평단, 종가):
    """매도 계획 계산 (익절 + 부분손절)"""
    
    매도계획 = []
    
    # ✅ 익절 로직: 현재가 > 평단 + 1%
    if 종가 > 평단 * 1.01:
        익절가1 = round(평단 * 1.01, 2)
        익절가2 = round(평단 * 1.015, 2)
        익절수량1 = int(보유개수 * 0.4)
        매도계획.append(("익절", 익절가1, 익절수량1))
        매도계획.append(("익절", 익절가2, -1))  # -1 = 나머지전부
    
    # ⚠️ 부분손절 로직: 현재가 < 평단이어도 VWAP 근처면 일부 손절
    # 원본방식: 손절 후 더 낮은가격에 재매수 → 평단 낮추기
    elif 종가 < 평단 * 0.99:  # 평단보다 1% 이상 낮을 때
        # VWAP 근처에서 일부 손절
        손절가 = round(vwap * 1.001, 2)
        손절수량 = int(보유개수 * 0.2)  # 보유량의 20% 손절
        if 손절수량 > 0:
            매도계획.append(("부분손절", 손절가, 손절수량))
    
    return 매도계획

def calculate_returns(잔금, 보유개수, 평단, 종가, 시즌2_실현수익, 시즌2_시작원금):
    """수익률 계산"""
    평가금액 = 보유개수 * 종가
    총자산 = 잔금 + 평가금액
    시즌2_수익률 = (시즌2_실현수익 / 시즌2_시작원금) * 100
    평가손익 = (종가 - 평단) * 보유개수
    return round(총자산, 2), round(시즌2_수익률, 2), round(평가손익, 2)

def send_telegram(msg):
    """텔레그램 메시지 전송"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    })
    return response.status_code == 200

def main():
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    
    print(f"실행시간: {now.strftime('%Y-%m-%d %H:%M')} KST")
    
    # 데이터 가져오기
    vwap, 종가 = get_soxl_data()
    
    # 매수 계획
    매수가1, 매수수량1, 매수가2, 매수수량2 = calculate_buy_plan(vwap, 잔금, 보유개수, 평단)
    
    # 매도 계획
    매도계획 = calculate_sell_plan(vwap, 보유개수, 평단, 종가)
    
    # 수익률
    총자산, 시즌2_수익률, 평가손익 = calculate_returns(잔금, 보유개수, 평단, 종가, 시즌2_실현수익, 시즌2_시작원금)
    
    # 매도 메시지 생성
    매도_메시지 = ""
    for 타입, 가격, 수량 in 매도계획:
        if 타입 == "익절":
            이모지 = "🟢"
            수량텍스트 = "나머지전부" if 수량 == -1 else f"{수량}개"
        else:
            이모지 = "🟡"
            수량텍스트 = f"{수량}개"
        매도_메시지 += f"\n{이모지} ${가격} × {수량텍스트} ({타입})"
    
    if not 매도_메시지:
        매도_메시지 = "\n⏸ 매도 조건 미충족 (보유 유지)"
    
    # 평단 대비 종가 상태
    if 종가 > 평단:
        상태 = f"📈 평단 위 (+${round(종가-평단, 2)})"
    else:
        상태 = f"📉 평단 아래 (-${round(평단-종가, 2)})"

    # 최종 메시지
    msg = f"""
📊 <b>SOXL 매매 계획 {now.strftime('%m/%d')}</b>

💰 <b>현재 상태</b>
├ 잔금: ${잔금:,.2f}
├ 보유: {보유개수}개
├ 평단: ${평단}
├ 전일종가: ${종가} {상태}
└ 평가손익: ${평가손익:+,.2f}

📈 <b>오늘 VWAP: ${vwap}</b>

🟢 <b>매수 계획</b>
├ ${매수가1} × {매수수량1}개
└ ${매수가2} × {매수수량2}개

🔴 <b>매도 계획</b>{매도_메시지}

📊 <b>수익 현황</b>
├ 시즌2 실현수익: ${시즌2_실현수익:,.2f}
├ 시즌2 수익률: {시즌2_수익률}%
└ 총 평가자산: ${총자산:,.2f}

⚡ 100개 미만은 30분 VWAP 일괄매매
    """
    
    success = send_telegram(msg)
    if success:
        print("✅ 텔레그램 전송 완료!")
    else:
        print("❌ 전송 실패")
    print(msg)

main()
