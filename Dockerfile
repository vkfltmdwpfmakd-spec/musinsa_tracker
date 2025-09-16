FROM python:3.10-slim

WORKDIR /code

# 필요한 OS 패키지 및 Playwright 브라우저 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN pip install playwright && playwright install --with-deps

# 4. 의존성 파일 복사 및 설치
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 5. 애플리케이션 코드 복사
COPY ./app /code/app

# 6. 서버 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]