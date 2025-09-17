from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from .database import engine, get_db
from .crawler import fetch_product_data 
from .category_crawler import fetch_category_products, fetch_multiple_categories, MUSINSA_CATEGORIES
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
    

    # 상품 기본 정보 (가격 제외)
    product_data = {
        'product_name': crawled_data['product_name'],
        'goods_no': crawled_data.get('goods_no'),
        'brand': crawled_data['brand'],
        'brand_english': crawled_data.get('brand_english'),
        'category': crawled_data.get('category'),
        'product_url': crawled_data['product_url'],
        'image_url': crawled_data['image_url'],
        'review_count': crawled_data.get('review_count', 0),
        'review_score': crawled_data.get('review_score', 0.0),
        'is_active': crawled_data.get('is_active', True)
    }

    # 상품 저장
    db_product = models.Product(**product_data)
    db.add(db_product)
    db.flush()  # ID 생성을 위해 flush

    # 가격 정보는 price_history에 저장
    price_history = models.PriceHistory(
        product_id=db_product.id,
        price=crawled_data.get('sale_price', 0),
        discount_price=crawled_data.get('sale_price', 0),
        discount_rate=crawled_data.get('discount_rate', 0),
        stock_status=crawled_data.get('stock_status', '재고 확인 필요'),
        is_sold_out=crawled_data.get('is_sold_out', False)
    )
    db.add(price_history)
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


@app.get("/categories")
async def get_categories():
    """무신사 카테고리 목록 조회"""

    return {
        "categories": MUSINSA_CATEGORIES,
        "total_count": len(MUSINSA_CATEGORIES)
    }

@app.post("/crawl/categories/{category_code}")
async def crawl_category(category_code: str, target_count: int = 300, save_to_db: bool = True, db: Session = Depends(get_db)):
    """특정 카테고리 상품 크롤링"""
    if category_code not in MUSINSA_CATEGORIES.values():
        raise HTTPException(
            status_code = 400,
            detail = f"유효하지 않은 카테고리 코드입니다. 지원 카테고리 : {list(MUSINSA_CATEGORIES.values())}"
        )

    try:
        products_data = await fetch_category_products(category_code, target_count)
        
        saved_products = []
        skipped_products = []

        if save_to_db:
            for product_data in products_data:
                # 이미 등록된 URL인지 확인
                existing_product = db.query(models.Product).filter(
                    models.Product.product_url == product_data['product_url']
                ).first()

                if existing_product:
                    skipped_products.append(product_data['product_url'])
                    continue

                # 상품 기본 정보 (가격 제외)
                db_product_data = {
                    'product_name': product_data['product_name'],
                    'goods_no': product_data.get('goods_no'),
                    'brand': product_data['brand'],
                    'brand_english': product_data.get('brand_english'),
                    'category': product_data.get('category'),
                    'category_depth1': product_data.get('category'),  # 1단계는 카테고리명과 동일
                    'product_url': product_data['product_url'],
                    'image_url': product_data['image_url'],
                    'review_count': product_data.get('review_count', 0),
                    'review_score': product_data.get('review_score', 0.0)
                }

                db_product = models.Product(**db_product_data)
                db.add(db_product)
                db.flush()  # ID 생성을 위해 flush

                # 가격 정보는 price_history에 저장
                price_history = models.PriceHistory(
                    product_id=db_product.id,
                    price=product_data.get('sale_price', 0),
                    discount_price=product_data.get('sale_price', 0),
                    discount_rate=product_data.get('discount_rate', 0),
                    stock_status="재고 확인 필요",
                    is_sold_out=False
                )
                db.add(price_history)
                saved_products.append(product_data['product_name'])

            db.commit()

        return {
            "message": f"카테고리 {category_code} 크롤링 완료",
            "crawled_count": len(products_data),
            "saved_count": len(saved_products),
            "skipped_count": len(skipped_products),
            "products": products_data if not save_to_db else saved_products
        }
    
    except Exception as e:
        raise HTTPException(
            status_code = 500,
            detail = f"크롤링 중 오류가 발생했습니다: {e}"
        )
    

@app.post("/crawl/categories")
async def crawl_multiple_categories(category_codes: List[str], target_count: int = 300, save_to_db: bool = True, db: Session = Depends(get_db)):
    """여러 카테고리 상품 크롤링 """

    # 유효한 카테고리 코드 확인
    invalid_codes = [code for code in category_codes if code not in MUSINSA_CATEGORIES.values()]
    if invalid_codes:
        raise HTTPException(
            status_code = 400,
            detail = f"유효하지 않은 카테고리 코드입니다. {invalid_codes}"
        )

    try:
        results = await fetch_multiple_categories(category_codes, target_count)

        total_crawled = 0
        total_saved = 0
        total_skipped = 0
        category_results = {}

        if save_to_db:
            for category_code, products_data in results.items():
                saved_products = []
                skipped_products = []

                for product_data in products_data:
                    # 이미 등록된 URL인지 확인
                    existing_product = db.query(models.Product).filter(
                        models.Product.product_url == product_data['product_url']
                    ).first()

                    if existing_product:
                        skipped_products.append(product_data['product_url'])
                        continue

                    # 상품 기본 정보 (가격 제외)
                    db_product_data = {
                        'product_name': product_data['product_name'],
                        'goods_no': product_data.get('goods_no'),
                        'brand': product_data['brand'],
                        'brand_english': product_data.get('brand_english'),
                        'category': product_data.get('category'),
                        'category_depth1': product_data.get('category'),  # 1단계는 카테고리명과 동일
                        'product_url': product_data['product_url'],
                        'image_url': product_data['image_url'],
                        'review_count': product_data.get('review_count', 0),
                        'review_score': product_data.get('review_score', 0.0)
                    }

                    db_product = models.Product(**db_product_data)
                    db.add(db_product)
                    db.flush()  # ID 생성을 위해 flush

                    # 가격 정보는 price_history에 저장
                    price_history = models.PriceHistory(
                        product_id=db_product.id,
                        price=product_data.get('sale_price', 0),
                        discount_price=product_data.get('sale_price', 0),
                        discount_rate=product_data.get('discount_rate', 0),
                        stock_status="재고 확인 필요",
                        is_sold_out=False
                    )
                    db.add(price_history)
                    saved_products.append(product_data['product_name'])

                category_results[category_code] = {
                    'crawled_count': len(products_data),
                    'saved_count': len(saved_products),
                    'skipped_count': len(skipped_products)
                }

                total_crawled += len(products_data)
                total_saved += len(saved_products)
                total_skipped += len(skipped_products)

            db.commit()
        else:
            for category_code, products_data in results.items():
                category_results[category_code] = {
                    'crawled_count': len(products_data),
                    'products': products_data
                }

                total_crawled += len(products_data)
        
        return {
            "message": f"{len(category_codes)}개 카테고리 크롤링 완료",
            "total_crawled": total_crawled,
            "total_saved": total_saved,
            "total_skipped": total_skipped,
            "category_results": category_results
        }
    
    except Exception as e:
        raise HTTPException(
            status_code = 500,
            detail = f"크롤링 중 오류가 발생했습니다: {e}"
        )


