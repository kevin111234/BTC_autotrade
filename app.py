from flask import Flask, render_template
import threading
import time
import json
import os
from src import realtrade  # realtrade.py 파일을 불러옴

app = Flask(__name__)

# 글로벌 변수로 거래 현황 및 수익률 저장
trade_data = {
    "total_profit": 0,   # 전체 수익률
    "last_trade_price": None,   # 최근 거래 가격
    "trades": []   # 거래 내역
}

# 포지션 데이터 로드
def load_trade_data():
    if os.path.exists('position.json'):
        with open('position.json', 'r') as f:
            return json.load(f)
    return None

# 자동투자 로직 실행
def auto_invest():
    while True:
        # realtrade.py에서의 자동 투자 전략 실행
        realtrade.execute_strategy()
        
        # 거래 데이터 업데이트 (position.json 파일을 로드)
        trade_data.update(load_trade_data())
        
        # 5분 간격으로 실행
        time.sleep(300)

# 백그라운드에서 자동투자 로직 실행 (서버 시작 시)
def start_background_task():
    thread = threading.Thread(target=auto_invest)
    thread.daemon = True
    thread.start()

@app.route('/')
def index():
    # 메인 화면에 거래 현황과 수익률 표시
    position = load_trade_data()
    return render_template('index.html', trade_data=position)

if __name__ == '__main__':
    # 백그라운드 작업 시작
    start_background_task()
    app.run(host='0.0.0.0', port=8080)
