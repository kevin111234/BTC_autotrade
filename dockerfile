# Step 1: 베이스 이미지 설정
FROM python:3.9-slim

# Step 2: 작업 디렉토리 설정
WORKDIR /app

# Step 3: 요구 사항 파일 복사 및 패키지 설치
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Step 4: 애플리케이션 코드 복사
COPY . .

# Step 5: Flask 애플리케이션 실행 (명령어 설정)
CMD ["python", "app.py"]
