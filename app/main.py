from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from .database import engine, get_db
from .crawler import fetch_product_data 
from . import models, schema




models.Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def read_root():
    """서버가 정상적으로 실행 중인지 확인하기 위한 테스트용"""
    return {"Hello": "World"}


@app.post("/products/", response_model=schema.Product)
async def create_product(product_url: str, db: Session = Depends(get_db)):
    """새로운 상품을 등록하고 크롤링해서 DB에 저장"""

    # 이미 등록된 URL인지 확인
    existing_product = db.query(models.Product).filter(
        models.Product.product_url == product_url
    ).first()

    if existing_product:
        raise HTTPException(
            status_code = 400,
            detail = "이미 등록된 상품입니다."
        )
    

    # 크롤링 실행
    crawled_data = await fetch_product_data(product_url)

    if not crawled_data:
        raise HTTPException(
            status_code = 400,
            detail = "크롤링 중 오류가 발생했습니다."
        )
    

    # DB에 저장
    db_product = models.Product(**crawled_data)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)

    return db_product

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
async def manual_crawl(product_id: int, db: Session = Depends(get_db)):
    """수동으로 상품 크롤링 실행"""

    # 상품 존재 여부 확인
    product = db.query(models.Product).filter(
        models.Product.id == product_id
        ).first()
    
    if not product:
        raise HTTPException(
            status_code = 404,
            detail = "상품을 찾을 수 없습니다."
        )
    
    # 크롤링 실행
    crawled_data = await fetch_product_data(product.product_url)

    if not crawled_data:
        raise HTTPException(
            status_code = 400,
            detail = "크롤링 중 오류가 발생했습니다."
        )


    # 상품정보 업데이트
    for key, value in crawled_data.items():
        if hasattr(product, key):
            setattr(product, key, value)
    

    # 가격 이력 저장
    price_history = models.PriceHistory(
        product_id = product.id,
        price = crawled_data['sale_price'],
        discount_price=crawled_data['sale_price'],
        discount_rate=crawled_data['discount_rate'],
        stock_status=crawled_data['stock_status'],
        is_sold_out=crawled_data['is_sold_out']
    )
    
    db.add(price_history)
    db.commit()
    db.refresh(price_history)

    return {
        "message": "크롤링 완료",
        "product_info": {
            "name": crawled_data['product_name'],
            "price": crawled_data['sale_price'],
            "stock_status": crawled_data['stock_status']
        },
        "price_history_id": price_history.id
    }


@app.get("/products/{product_id}/price_history", response_model=List[schema.PriceHistory])
async def get_price_history(product_id: int, db: Session = Depends(get_db)):
    """특정 상품의 가격 이력 조회"""
    product = db.query(models.Product).filter(
        models.Product.id == product_id
    ).first()

    if not product:
        raise HTTPException(
            status_code = 404,
            detail = "상품을 찾을 수 없습니다."
        )
    
    price_history = db.query(models.PriceHistory).filter(
        models.PriceHistory.product_id == product_id
    ).order_by(models.PriceHistory.crawled_at.desc()).all()

    return price_history


