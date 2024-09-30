import numpy as np
import pandas as pd
import pyupbit
import time
import datetime
import os
import json
from dotenv import load_dotenv
import logging

load_dotenv()

# 로그 설정
logging.basicConfig(filename='trading_bot.log', level=logging.INFO)

# API 키 설정
access_key = os.getenv('UPBIT_ACCESS_KEY')
secret_key = os.getenv('UPBIT_SECRET_KEY')
upbit = pyupbit.Upbit(access_key, secret_key)

# 최적의 파라미터 (백테스트 결과에서 가져오기)
best_params = {
    'ema_short': 15,
    'ema_long': 20,
    'rsi_period': 14,
    'bb_period': 20,
    'stop_loss': 0.1,
    'take_profit': 0.2
}

# 포지션 정보 로드 및 저장 함수
def save_position(position):
    with open('position.json', 'w') as f:
        json.dump(position, f)
    print("포지션 저장 완료")

def load_position():
    try:
        with open('position.json', 'r') as f:
            position = json.load(f)
            print("포지션 로드 완료")
            return position
    except FileNotFoundError:
        print("저장된 포지션 없음")
        return None

# 잔고 조회 함수
def get_balance(ticker):
    balances = upbit.get_balances()
    print("balances:", balances)
    if balances is None or not isinstance(balances, list):
        print("잔고 정보를 가져오지 못했습니다.")
        return 0
    for b in balances:
        print("b:", b)
        if 'currency' in b and b['currency'] == ticker.replace('KRW-', ''):
            balance = float(b['balance'])
            print(f"{ticker} 잔고: {balance}")
            return balance
    print(f"{ticker} 잔고: 0")
    return 0

# RSI 계산 함수
def compute_rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# 볼린저 밴드 계산 함수
def compute_bollinger_bands(series, period, num_std=2):
    sma = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper_band = sma + num_std * std
    lower_band = sma - num_std * std
    return upper_band, lower_band

# 데이터 로드 함수
def get_data(symbol='KRW-BTC', interval='minute5', count=200):
    print("데이터 로드 중...")
    df = pyupbit.get_ohlcv(symbol, interval=interval, count=count)
    df = df.reset_index()
    print("데이터 로드 완료")
    return df

# 거래 전략 실행 함수
def execute_strategy():
    try:
        print("전략 실행 시작")
        data = get_data()
        # 지표 계산
        print("지표 계산 중...")
        data['ema_short'] = data['close'].ewm(span=best_params['ema_short'], adjust=False).mean()
        data['ema_long'] = data['close'].ewm(span=best_params['ema_long'], adjust=False).mean()
        data['rsi'] = compute_rsi(data['close'], best_params['rsi_period'])
        data['bb_upper'], data['bb_lower'] = compute_bollinger_bands(data['close'], best_params['bb_period'])
        print("지표 계산 완료")

        # 최신 데이터 가져오기
        latest_data = data.iloc[-1]
        current_price = latest_data['close']
        print(f"현재 가격: {current_price}")

        # 포지션 로드
        position = load_position()

        # 매수 조건 확인
        print("매수 조건 확인 중...")
        if (latest_data['ema_short'] > latest_data['ema_long']) and \
            (latest_data['rsi'] < 30) and \
            (current_price <= latest_data['bb_lower']):
            print("매수 조건 충족")
            if position is None:
                krw_balance = get_balance('KRW')
                if krw_balance > 5000:
                    # 매수 주문
                    print("매수 주문 실행 중...")
                    buy_amount = krw_balance * 0.9995
                    buy_result = upbit.buy_market_order('KRW-BTC', buy_amount)
                    logging.info(f"매수 주문 실행: 가격={current_price}, 시간={datetime.datetime.now()}")
                    print(f"매수 주문 실행: 가격={current_price}, 시간={datetime.datetime.now()}")
                    # 포지션 저장
                    position = {
                        'price': current_price,
                        'stop_price': current_price * (1 - best_params['stop_loss']),
                        'take_price': current_price * (1 + best_params['take_profit'])
                    }
                    save_position(position)
                else:
                    print("주문 가능 잔고 부족")
            else:
                print("이미 포지션 보유 중")
        else:
            print("매수 조건 미충족")

        # 매도 조건 확인
        print("매도 조건 확인 중...")
        btc_balance = get_balance('BTC')
        if position is not None and btc_balance > 0:
            if current_price >= position['take_price']:
                # 이익 실현 매도
                print("이익 실현 매도 조건 충족")
                print("매도 주문 실행 중...")
                sell_result = upbit.sell_market_order('KRW-BTC', btc_balance)
                logging.info(f"이익 실현 매도 주문 실행: 가격={current_price}, 시간={datetime.datetime.now()}")
                print(f"이익 실현 매도 주문 실행: 가격={current_price}, 시간={datetime.datetime.now()}")
                # 포지션 삭제
                save_position(None)
            elif current_price <= position['stop_price']:
                # 손절 매도
                print("손절 매도 조건 충족")
                print("매도 주문 실행 중...")
                sell_result = upbit.sell_market_order('KRW-BTC', btc_balance)
                logging.info(f"손절 매도 주문 실행: 가격={current_price}, 시간={datetime.datetime.now()}")
                print(f"손절 매도 주문 실행: 가격={current_price}, 시간={datetime.datetime.now()}")
                # 포지션 삭제
                save_position(None)
            else:
                print("매도 조건 미충족")
        else:
            print("포지션 없음 또는 BTC 잔고 없음")

        print("전략 실행 완료")

    except Exception as e:
        logging.error(f"에러 발생: {e}")
        print(f"에러 발생: {e}")
        time.sleep(60)  # 오류 발생 시 1분 대기

# 메인 루프 실행
while True:
    execute_strategy()
    print("다음 실행까지 대기 중...")
    time.sleep(300)  # 5분 대기
