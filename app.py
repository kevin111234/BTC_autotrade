from flask import Flask, render_template
import threading
import time
import os
import json
import requests
from dotenv import load_dotenv
from src import realtrade  # realtrade.py에서 투자 로직 가져옴
import slack_sdk

# Flask 서버 초기화
app = Flask(__name__)

# 환경 변수 로드
load_dotenv()
slack_token = os.getenv('SLACK_API_TOKEN')
slack_channel = os.getenv('SLACK_CHANNEL_ID')

# Slack 메시지 전송 함수
def notice_message(token, channel, text, attachments):
    attachments = json.dumps(attachments)
    response = requests.post("https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer " + token},
        data={"channel": channel, "text": text, "attachments": attachments})

# 거래 상황을 알릴 메시지 생성 함수
def create_trade_message(trade_type, price, time):
    title = f"{time} - {trade_type} 알림"
    link = "https://www.upbit.com/exchange?code=CRIX.UPBIT.KRW-BTC"
    text = f'''
    거래유형: {trade_type}
    거래가격: {price} KRW
    '''

    attach_dict = {
        'color': '#36a64f' if trade_type == '매수' else '#ff0000',
        'author_name': 'Auto-Trade Bot',
        'title': title,
        'title_link': link,
        'text': text
    }
    attach_list = [attach_dict]
    return attach_list

# 매수 및 매도 시 Slack에 알림 전송
def send_trade_notification(trade_type, price):
    time_now = realtrade.datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message_text = f"{time_now} - {trade_type} 거래가 발생했습니다."
    attachments = create_trade_message(trade_type, price, time_now)
    notice_message(slack_token, slack_channel, message_text, attachments)

# 자동투자 로직 실행
def execute_strategy():
    try:
        print("전략 실행 시작")
        data = realtrade.get_data()
        latest_data = data.iloc[-1]
        current_price = latest_data['close']
        position = realtrade.load_position()

        # 매수 조건 확인
        if (latest_data['ema_short'] > latest_data['ema_long']) and \
          (latest_data['rsi'] < 30) and \
          (current_price <= latest_data['bb_lower']):
            if position is None:
                krw_balance = realtrade.get_balance('KRW')
                if krw_balance > 5000:
                    # 매수 주문
                    buy_amount = krw_balance * 0.9995
                    buy_result = realtrade.upbit.buy_market_order('KRW-BTC', buy_amount)
                    realtrade.save_position({
                        'price': current_price,
                        'stop_price': current_price * (1 - realtrade.best_params['stop_loss']),
                        'take_price': current_price * (1 + realtrade.best_params['take_profit'])
                    })
                    send_trade_notification('매수', current_price)

        # 매도 조건 확인
        btc_balance = realtrade.get_balance('BTC')
        if position is not None and btc_balance > 0:
            if current_price >= position['take_price']:
                # 이익 실현 매도
                sell_result = realtrade.upbit.sell_market_order('KRW-BTC', btc_balance)
                realtrade.save_position(None)
                send_trade_notification('이익 실현 매도', current_price)
            elif current_price <= position['stop_price']:
                # 손절 매도
                sell_result = realtrade.upbit.sell_market_order('KRW-BTC', btc_balance)
                realtrade.save_position(None)
                send_trade_notification('손절 매도', current_price)

    except Exception as e:
        realtrade.logging.error(f"에러 발생: {e}")
        print(f"에러 발생: {e}")
        time.sleep(60)

# 백그라운드에서 자동투자 로직 실행 (5분 간격)
def start_auto_trading():
    while True:
        execute_strategy()
        time.sleep(300)  # 5분 대기

# 백그라운드 작업을 위한 스레드 실행
def start_background_task():
    thread = threading.Thread(target=start_auto_trading)
    thread.daemon = True
    thread.start()

# 메인 페이지에서 거래 정보 표시
@app.route('/')
def index():
    position = realtrade.load_position()  # 현재 포지션 로드
    return render_template('index.html', trade_data=position)

# Flask 서버 실행
if __name__ == '__main__':
    start_background_task()  # 백그라운드에서 자동 투자 로직 시작
    app.run(host='0.0.0.0', port=8080)
