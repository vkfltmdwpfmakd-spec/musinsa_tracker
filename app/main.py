from fastapi import FastAPI, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from typing import List
from datetime import timedelta
from .database import engine, get_db
from .auth import get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from .scheduler import start_scheduler, stop_scheduler, get_scheduler_status
from .services import (
    create_product_from_url,
    crawl_and_save_multiple_categories,
    update_product_prices,
    manual_crawl_product
)
from .category_crawler import MUSINSA_CATEGORIES
from . import models, schema
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded




models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="무신사 가격 트래커 API", version="1.0.0")

# Rate Limiter 설정
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 앱 시작 시 스케줄러 시작
@app.on_event("startup")
async def startup_event():
    start_scheduler()

# 앱 종료 시 스케줄러 중지
@app.on_event("shutdown")
async def shutdown_event():
    stop_scheduler()


@app.get("/")
def read_root():
    """서버가 정상적으로 실행 중인지 확인하기 위한 테스트용"""
    return {"Hello": "World"}


# 인증 관련 엔드포인트
@app.post("/auth/token")
async def login_for_access_token(username: str = "admin", password: str = "password"):
    """JWT 토큰 발급 (개발용 - 실제로는 사용자 DB 연동 필요)"""
    # 실제 환경에서는 사용자 DB에서 검증해야 함
    if username == "admin" and password == "password":
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": username}, expires_delta=access_token_expires
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    else:
        raise HTTPException(
            status_code=401,
            detail="잘못된 사용자명 또는 비밀번호입니다",
            headers={"WWW-Authenticate": "Bearer"},
        )


# 스케줄러 관리 엔드포인트
@app.get("/scheduler/status")
@limiter.limit("10/minute")
async def get_scheduler_info(request: Request, current_user: str = Depends(get_current_user)):
    """스케줄러 상태 및 작업 목록 조회"""
    return get_scheduler_status()


@app.post("/products/", response_model=schema.Product)
@limiter.limit("5/minute")
async def create_product(
    request: Request,
    product_url: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """새로운 상품을 등록하고 크롤링해서 DB에 저장"""
    try:
        # services.py의 비즈니스 로직 사용
        db_product = await create_product_from_url(product_url, db)
        return db_product
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")

@app.get("/products/", response_model=List[schema.Product])
async def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """등록된 상품 목록 조회"""
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return products


@app.get("/products/{product_id}", response_model=schema.Product)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """특정 상품 조회"""
    product = db.query(models.Product).filter(
        models.Product.id == product_id
        ).first()
    
    if not product:
        raise HTTPException(
            status_code = 404,
            detail = "상품을 찾을 수 없습니다."
        )
    
    return product


@app.delete("/products/{product_id}")
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    """상품 삭제"""
    product = db.query(models.Product).filter(
        models.Product.id == product_id
        ).first()
    
    if not product:
        raise HTTPException(
            status_code = 404,
            detail = "상품을 찾을 수 없습니다."
        )
    
    db.delete(product)
    db.commit()
    return {"message": f"상품 '{product.product_name}' 삭제되었습니다."}
    

@app.post("/products/{product_id}/crawl")
@limiter.limit("10/minute")
async def manual_crawl(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """수동으로 상품 크롤링 실행"""
    try:
        # services.py의 비즈니스 로직 사용
        result = await manual_crawl_product(product_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.post("/crawl/categories")
@limiter.limit("3/minute")
async def crawl_multiple_categories_endpoint(
    request: Request,
    category_codes: List[str],
    target_count: int = 300,
    save_to_db: bool = True,
    db: Session = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """여러 카테고리 상품 크롤링"""
    try:
        # services.py의 비즈니스 로직 사용
        result = await crawl_and_save_multiple_categories(
            category_codes=category_codes,
            target_count=target_count,
            save_to_db=save_to_db,
            db=db
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")


@app.get("/categories")
async def get_categories():
    """지원하는 카테고리 목록 조회"""
    return {
        "categories": MUSINSA_CATEGORIES,
        "total_count": len(MUSINSA_CATEGORIES)
    }


@app.get("/products/{product_id}/price_history", response_model=List[schema.PriceHistory])
async def get_price_history(product_id: int, db: Session = Depends(get_db)):
    """특정 상품의 가격 이력 조회"""
    product = db.query(models.Product).filter(
        models.Product.id == product_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=404,
            detail="상품을 찾을 수 없습니다."
        )

    price_history = db.query(models.PriceHistory).filter(
        models.PriceHistory.product_id == product_id
    ).order_by(models.PriceHistory.crawled_at.desc()).all()

    return price_history


