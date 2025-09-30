# 무신사 가격 트래커

무신사 온라인 쇼핑몰의 상품 가격을 자동으로 추적하고 분석하는 데이터 파이프라인 시스템입니다.

## 프로젝트 소개

이 프로젝트는 무신사 상품의 가격 변동을 실시간으로 모니터링하고, 수집된 데이터를 기반으로 비즈니스 인사이트를 제공하는 데이터 엔지니어링 솔루션입니다. 웹 크롤링부터 데이터 저장, 분석, 시각화까지 전체 데이터 파이프라인을 구현했습니다.

## 주요 기능

### 데이터 수집
- 개별 상품 URL 기반 상세 정보 크롤링
- 카테고리별 대량 상품 자동 수집
- 가격, 할인율, 재고 상태, 리뷰 정보 추출
- 스케줄링 기반 자동 데이터 업데이트

### 데이터 분석
- 대시보드 요약 통계 (총 상품 수, 브랜드 수, 리뷰 커버리지)
- 브랜드별 성과 분석 (평균 가격, 리뷰 점수, 상품 수)
- 카테고리별 시장 분석 (가격 범위, 인기도)
- 가격 트렌드 분석 (할인율, 가격 변동)
- 고평점 상품 및 트렌딩 상품 추천

### 모니터링 시스템
- Prometheus 기반 메트릭 수집
- Grafana 대시보드를 통한 실시간 시각화
- 시스템 리소스 및 크롤링 성능 추적
- API 응답시간 및 처리량 모니터링

## 기술 스택

### Backend
- **FastAPI**: REST API 서버 프레임워크
- **SQLAlchemy**: ORM 및 데이터베이스 모델링
- **PostgreSQL**: 관계형 데이터베이스
- **Pydantic**: 데이터 검증 및 직렬화

### 데이터 수집
- **Playwright**: 브라우저 자동화 및 웹 크롤링
- **APScheduler**: 스케줄링 작업 관리
- **Asyncio**: 비동기 처리를 통한 성능 최적화

### 모니터링
- **Prometheus**: 메트릭 수집 및 저장
- **Grafana**: 데이터 시각화 대시보드
- **psutil**: 시스템 리소스 모니터링

### 인프라
- **Docker**: 컨테이너화
- **Docker Compose**: 멀티 컨테이너 오케스트레이션

## 프로젝트 구조

```
musinsa_tracker/
├── app/
│   ├── main.py                 # FastAPI 애플리케이션 및 라우터
│   ├── models.py               # SQLAlchemy 데이터베이스 모델
│   ├── schema.py               # Pydantic 스키마 정의
│   ├── database.py             # 데이터베이스 연결 설정
│   ├── auth.py                 # JWT 인증 및 보안
│   ├── crawler.py              # 개별 상품 크롤링 로직
│   ├── category_crawler.py     # 카테고리 크롤링 로직
│   ├── services.py             # 비즈니스 로직 서비스
│   ├── analytics.py            # 데이터 분석 API
│   ├── monitoring.py           # Prometheus 메트릭 수집
│   └── scheduler.py            # 스케줄링 작업 관리
├── monitoring/
│   ├── prometheus.yml          # Prometheus 설정
│   └── grafana/
│       ├── datasources/        # Grafana 데이터소스 설정
│       └── dashboards/         # 대시보드 프로비저닝
├── docker-compose.yml          # 서비스 오케스트레이션
├── Dockerfile                  # 애플리케이션 이미지
├── requirements.txt            # Python 의존성
└── .env.example               # 환경변수 템플릿
```

## 설치 및 실행

### 사전 요구사항
- Docker 및 Docker Compose
- Python 3.10 이상 (로컬 개발 시)

### 환경 설정

1. 저장소 클론
```bash
git clone <repository-url>
cd musinsa_tracker
```

2. 환경변수 설정
```bash
cp .env.example .env
# .env 파일을 편집하여 필요한 값들을 설정
```

3. Docker 환경 실행
```bash
docker-compose up -d --build
```

### 서비스 접근
- API 문서: http://localhost:8000/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

## 데이터베이스 설계

### 주요 테이블

**products 테이블**
- 상품 기본 정보 (상품명, 브랜드, 카테고리)
- 리뷰 정보 (개수, 평점)
- 상품 URL 및 이미지 URL

**price_history 테이블**
- 가격 변동 이력 추적
- 정상가, 판매가, 할인율
- 크롤링 시점 기록

## API 엔드포인트

### 상품 관리
```
POST   /products/              # 상품 등록 및 크롤링
GET    /products/              # 상품 목록 조회
GET    /products/{id}          # 상품 상세 조회
DELETE /products/{id}          # 상품 삭제
POST   /products/{id}/crawl    # 수동 크롤링
```

### 크롤링
```
GET    /categories             # 카테고리 목록 조회
POST   /crawl/categories       # 카테고리 크롤링
```

### 분석
```
GET    /analytics/dashboard         # 대시보드 요약 통계
GET    /analytics/brands            # 브랜드별 분석
GET    /analytics/categories        # 카테고리별 분석
GET    /analytics/price-trends      # 가격 트렌드 분석
GET    /analytics/reviews           # 리뷰 분석
GET    /analytics/products/top-rated    # 고평점 상품
GET    /analytics/products/trending     # 트렌딩 상품
```

### 스케줄러
```
GET    /scheduler/status       # 스케줄러 상태 확인
```

## 개발 환경 설정

### 로컬 개발
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 데이터베이스만 Docker로 실행
docker-compose up -d db

# 환경변수 설정
export DATABASE_URL=postgresql://user:password@localhost:5432/musinsa_db

# 애플리케이션 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 데이터베이스 직접 접속
```bash
docker-compose exec db psql -U user -d musinsa_db
```

## 아키텍처 특징

### 스케일러블 크롤링
- 비동기 처리를 통한 고성능 크롤링
- 동적 카테고리 시스템으로 웹사이트 변경에 대응
- Rate limiting을 통한 안전한 크롤링

### 견고한 데이터 파이프라인
- 중복 제거 및 데이터 검증
- 단계별 에러 처리 및 로깅
- 트랜잭션 기반 데이터 무결성 보장

### 실시간 모니터링
- 시스템 메트릭 및 비즈니스 메트릭 수집
- 대시보드를 통한 실시간 시각화
- 알림 및 임계값 관리

## 보안 기능

- JWT 기반 인증 및 인가
- API 키 기반 대체 인증
- Rate limiting을 통한 API 보호
- 환경변수를 통한 설정 분리
- 토큰 블랙리스트 관리

## 성능 최적화

- 비동기 처리를 통한 동시성 향상
- 데이터베이스 인덱싱 최적화
- 캐싱을 통한 응답 시간 단축
- 배치 처리를 통한 효율성 증대

## 데이터 분석 결과

현재 시스템에서 수집한 데이터 기준:
- 총 상품 수: 900개
- 브랜드 수: 417개
- 리뷰 커버리지: 77.9%
- 평균 할인율: 33.4%
- API 평균 응답시간: 91ms

## 향후 개선 계획

- 머신러닝 기반 가격 예측 모델
- 실시간 알림 시스템
- 더 많은 쇼핑몰 지원
- 모바일 앱 개발
- 사용자 개인화 기능

## 문제 해결

### 크롤링 이슈
```bash
# 브라우저 설치
docker-compose run api playwright install --with-deps

# 로그 확인
docker-compose logs -f api
```

### 데이터베이스 연결 이슈
```bash
# 컨테이너 상태 확인
docker-compose ps

# 데이터베이스 로그 확인
docker-compose logs db
```
