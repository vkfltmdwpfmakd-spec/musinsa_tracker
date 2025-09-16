import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# 데이터베이스 연결 엔진 생성
engine = create_engine(DATABASE_URL)

# 데이터베이스 세션 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 기본 베이스 설정
Base = declarative_base()


def get_db():
    db = SessionLocal() # 세션 생성
    try:
        # yield 키워드를 사용하여 생성된 세션(db)을 API 경로 함수에 전달
        yield db
    finally:
        # API 요청 처리가 끝나면 (성공/실패 여부와 관계없이) 세션을 닫아 리소스를 반환
        db.close()
