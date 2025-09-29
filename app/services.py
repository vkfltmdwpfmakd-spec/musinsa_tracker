import asyncio
import logging
from sqlalchemy.orm import Session
from typing import List, Dict, Tuple
from .crawler import fetch_product_data
from .category_crawler import fetch_multiple_categories, get_cached_categories
from . import models
from .monitoring import track_crawling_metrics

# 로깅 설정
logger = logging.getLogger(__name__)


async def create_product_from_url(product_url: str, db: Session) -> models.Product:
    """개별 상품 URL로부터 상품 생성 및 저장"""

    # 이미 등록된 URL인지 확인
    existing_product = db.query(models.Product).filter(
        models.Product.product_url == product_url
    ).first()

    if existing_product:
        raise ValueError("이미 등록된 상품입니다.")

    # 크롤링 실행
    crawled_data = await fetch_product_data(product_url)

    if not crawled_data:
        raise ValueError("크롤링 중 오류가 발생했습니다.")

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
        normal_price=crawled_data.get('normal_price', 0),
        sale_price=crawled_data.get('sale_price', 0),
        discount_rate=crawled_data.get('discount_rate', 0),
        is_sold_out=crawled_data.get('is_sold_out', False)
    )
    db.add(price_history)
    db.commit()
    db.refresh(db_product)

    return db_product

@track_crawling_metrics("multiple")
async def crawl_and_save_multiple_categories(
    category_codes: List[str],
    target_count: int = 300,
    save_to_db: bool = True,
    db: Session = None
) -> Dict:
    """여러 카테고리 상품 크롤링 및 DB 저장"""

    # 유효한 카테고리 코드 확인 (동적 카테고리 사용)
    musinsa_categories = await get_cached_categories()
    invalid_codes = [code for code in category_codes if code not in musinsa_categories.values()]
    if invalid_codes:
        raise ValueError(f"유효하지 않은 카테고리 코드입니다: {invalid_codes}")

    # 카테고리 크롤링 실행
    results = await fetch_multiple_categories(category_codes, target_count)

    total_crawled = 0
    total_saved = 0
    total_skipped = 0
    category_results = {}

    if save_to_db and db:
        for category_code, products_data in results.items():
            crawled_count = len(products_data)
            saved_count = 0
            skipped_count = 0

            logger.info(f"카테고리 {category_code}: {crawled_count}개 상품 처리 중")

            for product_info in products_data:
                try:
                    # 중복 확인 (URL 기준)
                    product_url = product_info.get('product_url')
                    if not product_url:
                        continue

                    existing_product = db.query(models.Product).filter(
                        models.Product.product_url == product_url
                    ).first()

                    if existing_product:
                        skipped_count += 1
                        continue

                    # 새로운 상품 저장
                    product_data = {
                        'product_name': product_info.get('product_name'),
                        'goods_no': product_info.get('goods_no'),
                        'brand': product_info.get('brand'),
                        'brand_english': product_info.get('brand_english'),
                        'category': product_info.get('category'),
                        'product_url': product_url,
                        'image_url': product_info.get('image_url'),
                        'review_count': product_info.get('review_count', 0),
                        'review_score': product_info.get('review_score', 0.0),
                        'is_active': True
                    }

                    db_product = models.Product(**product_data)
                    db.add(db_product)
                    db.flush()  # ID 생성을 위해 flush

                    # 가격 이력 저장
                    price_history = models.PriceHistory(
                        product_id=db_product.id,
                        normal_price=product_info.get('normal_price', 0),
                        sale_price=product_info.get('sale_price', 0),
                        discount_rate=product_info.get('discount_rate', 0),
                        is_sold_out=product_info.get('is_sold_out', False)
                    )
                    db.add(price_history)
                    saved_count += 1

                except Exception as e:
                    logger.error(f"상품 저장 중 오류: {str(e)}")
                    continue

            total_crawled += crawled_count
            total_saved += saved_count
            total_skipped += skipped_count

            category_results[category_code] = {
                "crawled": crawled_count,
                "saved": saved_count,
                "skipped": skipped_count
            }

        # 변경사항 커밋
        db.commit()

    else:
        # DB 저장 없이 크롤링만
        for category_code, products_data in results.items():
            crawled_count = len(products_data)
            total_crawled += crawled_count
            category_results[category_code] = {
                "crawled": crawled_count,
                "saved": 0,
                "skipped": 0
            }

    return {
        "message": "카테고리 크롤링 완료",
        "total_crawled": total_crawled,
        "total_saved": total_saved,
        "total_skipped": total_skipped,
        "category_results": category_results,
        "raw_data": results if not save_to_db else None
    }


async def update_product_prices(db: Session) -> Dict:
    """등록된 모든 활성 상품의 가격 정보 업데이트"""

    # 활성화된 모든 상품 조회
    active_products = db.query(models.Product).filter(
        models.Product.is_active == True
    ).all()

    logger.info(f"가격 업데이트 시작: {len(active_products)}개 상품")

    success_count = 0
    error_count = 0
    results = []

    for product in active_products:
        try:
            # 개별 상품 크롤링
            crawled_data = await fetch_product_data(product.product_url)

            if crawled_data:
                # 가격 이력 저장
                price_history = models.PriceHistory(
                    product_id=product.id,
                    normal_price=crawled_data.get('normal_price', 0),
                    sale_price=crawled_data.get('sale_price', 0),
                    discount_rate=crawled_data.get('discount_rate', 0),
                    is_sold_out=crawled_data.get('is_sold_out', False)
                )

                db.add(price_history)
                success_count += 1
                results.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "status": "success",
                    "price": crawled_data.get('sale_price', 0)
                })
            else:
                error_count += 1
                results.append({
                    "product_id": product.id,
                    "product_name": product.product_name,
                    "status": "failed",
                    "error": "크롤링 실패"
                })

            # 과부하 방지를 위한 딜레이
            await asyncio.sleep(2)

        except Exception as e:
            error_count += 1
            results.append({
                "product_id": product.id,
                "product_name": product.product_name,
                "status": "error",
                "error": str(e)
            })

    # 변경사항 커밋
    db.commit()

    return {
        "message": "가격 업데이트 완료",
        "total_products": len(active_products),
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }


async def manual_crawl_product(product_id: int, db: Session) -> Dict:
    """특정 상품 수동 크롤링"""

    # 상품 조회
    product = db.query(models.Product).filter(
        models.Product.id == product_id
    ).first()

    if not product:
        raise ValueError("상품을 찾을 수 없습니다.")

    try:
        # 크롤링 실행
        crawled_data = await fetch_product_data(product.product_url)

        if not crawled_data:
            raise ValueError("크롤링 중 오류가 발생했습니다.")

        # 가격 이력 저장
        price_history = models.PriceHistory(
            product_id=product.id,
            normal_price=crawled_data.get('normal_price', 0),
            sale_price=crawled_data.get('sale_price', 0),
            discount_rate=crawled_data.get('discount_rate', 0),
            is_sold_out=crawled_data.get('is_sold_out', False)
        )

        db.add(price_history)
        db.commit()

        return {
            "message": "수동 크롤링 완료",
            "product_id": product.id,
            "product_name": product.product_name,
            "price": crawled_data.get('sale_price', 0),
            "stock_status": crawled_data.get('stock_status', '재고 확인 필요'),
            "crawled_at": price_history.crawled_at
        }

    except Exception as e:
        raise ValueError(f"크롤링 중 오류가 발생했습니다: {e}")