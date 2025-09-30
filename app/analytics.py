import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from . import models
import pytz

# 로깅 설정
logger = logging.getLogger(__name__)

# 한국 시간대
KST = pytz.timezone('Asia/Seoul')


async def get_price_trends(
    db: Session,
    product_id: Optional[int] = None,
    days: int = 7
) -> Dict:
    """가격 트렌드 분석"""

    try:
        # 기간 설정
        end_date = datetime.now(KST)
        start_date = end_date - timedelta(days=days)

        # 특정 상품의 가격 트렌드
        if product_id:
            query = db.query(
                models.PriceHistory.crawled_at,
                models.PriceHistory.normal_price,
                models.PriceHistory.sale_price,
                models.PriceHistory.discount_rate,
                models.Product.product_name
            ).join(
                models.Product, models.PriceHistory.product_id == models.Product.id
            ).filter(
                models.PriceHistory.product_id == product_id,
                models.PriceHistory.crawled_at >= start_date
            ).order_by(models.PriceHistory.crawled_at)

            price_data = query.all()

            return {
                "product_id": product_id,
                "period_days": days,
                "data_points": len(price_data),
                "price_history": [
                    {
                        "timestamp": record.crawled_at.isoformat(),
                        "product_name": record.product_name,
                        "normal_price": record.normal_price,
                        "sale_price": record.sale_price,
                        "discount_rate": record.discount_rate
                    }
                    for record in price_data
                ]
            }

        # 전체 가격 트렌드 통계
        else:
            # 평균 할인율 트렌드
            avg_discount = db.query(
                func.avg(models.PriceHistory.discount_rate).label('avg_discount'),
                func.date(models.PriceHistory.crawled_at).label('date')
            ).filter(
                models.PriceHistory.crawled_at >= start_date
            ).group_by(
                func.date(models.PriceHistory.crawled_at)
            ).order_by('date').all()

            # 평균 가격 트렌드
            avg_prices = db.query(
                func.avg(models.PriceHistory.sale_price).label('avg_sale_price'),
                func.avg(models.PriceHistory.normal_price).label('avg_normal_price'),
                func.date(models.PriceHistory.crawled_at).label('date')
            ).filter(
                models.PriceHistory.crawled_at >= start_date,
                models.PriceHistory.sale_price > 0
            ).group_by(
                func.date(models.PriceHistory.crawled_at)
            ).order_by('date').all()

            return {
                "period_days": days,
                "average_discount_trend": [
                    {
                        "date": record.date.isoformat(),
                        "avg_discount_rate": float(record.avg_discount) if record.avg_discount else 0
                    }
                    for record in avg_discount
                ],
                "average_price_trend": [
                    {
                        "date": record.date.isoformat(),
                        "avg_sale_price": float(record.avg_sale_price) if record.avg_sale_price else 0,
                        "avg_normal_price": float(record.avg_normal_price) if record.avg_normal_price else 0
                    }
                    for record in avg_prices
                ]
            }

    except Exception as e:
        logger.error(f"가격 트렌드 분석 중 오류: {str(e)}")
        raise


async def get_brand_statistics(db: Session, limit: int = 20) -> Dict:
    """브랜드별 통계 분석"""

    try:
        # 브랜드별 상품 수 및 평균 가격
        brand_stats = db.query(
            models.Product.brand,
            func.count(models.Product.id).label('product_count'),
            func.avg(models.Product.review_score).label('avg_review_score'),
            func.avg(models.Product.review_count).label('avg_review_count')
        ).filter(
            models.Product.brand.isnot(None),
            models.Product.brand != ''
        ).group_by(
            models.Product.brand
        ).order_by(
            desc('product_count')
        ).limit(limit).all()

        # 브랜드별 최신 평균 가격 (서브쿼리 사용)
        latest_prices_subquery = db.query(
            models.PriceHistory.product_id,
            func.max(models.PriceHistory.crawled_at).label('latest_crawled')
        ).group_by(models.PriceHistory.product_id).subquery()

        brand_price_stats = db.query(
            models.Product.brand,
            func.avg(models.PriceHistory.sale_price).label('avg_sale_price'),
            func.avg(models.PriceHistory.discount_rate).label('avg_discount_rate')
        ).join(
            models.PriceHistory, models.Product.id == models.PriceHistory.product_id
        ).join(
            latest_prices_subquery,
            (models.PriceHistory.product_id == latest_prices_subquery.c.product_id) &
            (models.PriceHistory.crawled_at == latest_prices_subquery.c.latest_crawled)
        ).filter(
            models.Product.brand.isnot(None),
            models.Product.brand != '',
            models.PriceHistory.sale_price > 0
        ).group_by(
            models.Product.brand
        ).all()

        # 브랜드별 가격 정보를 딕셔너리로 변환
        price_dict = {
            brand: {
                'avg_sale_price': float(avg_price) if avg_price else 0,
                'avg_discount_rate': float(avg_discount) if avg_discount else 0
            }
            for brand, avg_price, avg_discount in brand_price_stats
        }

        return {
            "total_brands": len(brand_stats),
            "brand_statistics": [
                {
                    "brand": record.brand,
                    "product_count": record.product_count,
                    "avg_review_score": float(record.avg_review_score) if record.avg_review_score else 0,
                    "avg_review_count": float(record.avg_review_count) if record.avg_review_count else 0,
                    "avg_sale_price": price_dict.get(record.brand, {}).get('avg_sale_price', 0),
                    "avg_discount_rate": price_dict.get(record.brand, {}).get('avg_discount_rate', 0)
                }
                for record in brand_stats
            ]
        }

    except Exception as e:
        logger.error(f"브랜드 통계 분석 중 오류: {str(e)}")
        raise


async def get_category_insights(db: Session, limit: int = 15) -> Dict:
    """카테고리별 인사이트 분석"""

    try:
        # 카테고리별 기본 통계
        category_stats = db.query(
            models.Product.category,
            func.count(models.Product.id).label('product_count'),
            func.avg(models.Product.review_score).label('avg_review_score'),
            func.sum(models.Product.review_count).label('total_reviews')
        ).filter(
            models.Product.category.isnot(None),
            models.Product.category != ''
        ).group_by(
            models.Product.category
        ).order_by(
            desc('product_count')
        ).limit(limit).all()

        # 카테고리별 가격 범위 분석
        category_price_analysis = db.query(
            models.Product.category,
            func.min(models.PriceHistory.sale_price).label('min_price'),
            func.max(models.PriceHistory.sale_price).label('max_price'),
            func.avg(models.PriceHistory.sale_price).label('avg_price'),
            func.avg(models.PriceHistory.discount_rate).label('avg_discount')
        ).join(
            models.PriceHistory, models.Product.id == models.PriceHistory.product_id
        ).filter(
            models.Product.category.isnot(None),
            models.Product.category != '',
            models.PriceHistory.sale_price > 0
        ).group_by(
            models.Product.category
        ).all()

        # 카테고리별 가격 정보를 딕셔너리로 변환
        price_analysis_dict = {
            category: {
                'min_price': int(min_price) if min_price else 0,
                'max_price': int(max_price) if max_price else 0,
                'avg_price': int(avg_price) if avg_price else 0,
                'avg_discount': float(avg_discount) if avg_discount else 0
            }
            for category, min_price, max_price, avg_price, avg_discount in category_price_analysis
        }

        return {
            "total_categories": len(category_stats),
            "category_insights": [
                {
                    "category": record.category,
                    "product_count": record.product_count,
                    "avg_review_score": float(record.avg_review_score) if record.avg_review_score else 0,
                    "total_reviews": record.total_reviews if record.total_reviews else 0,
                    "price_analysis": price_analysis_dict.get(record.category, {
                        'min_price': 0, 'max_price': 0, 'avg_price': 0, 'avg_discount': 0
                    })
                }
                for record in category_stats
            ]
        }

    except Exception as e:
        logger.error(f"카테고리 인사이트 분석 중 오류: {str(e)}")
        raise


async def get_review_analysis(db: Session) -> Dict:
    """리뷰 점수 분석"""

    try:
        # 리뷰 점수 분포
        review_distribution = db.query(
            models.Product.review_score,
            func.count(models.Product.id).label('count')
        ).filter(
            models.Product.review_score > 0
        ).group_by(
            models.Product.review_score
        ).order_by(
            models.Product.review_score
        ).all()

        # 리뷰 수 기준 통계
        review_count_stats = db.query(
            func.avg(models.Product.review_count).label('avg_review_count'),
            func.max(models.Product.review_count).label('max_review_count'),
            func.min(models.Product.review_count).label('min_review_count'),
            func.count(models.Product.id).filter(models.Product.review_count > 0).label('products_with_reviews'),
            func.count(models.Product.id).label('total_products')
        ).first()

        # 고평점 상품 (4.5점 이상)
        high_rated_products = db.query(
            models.Product.product_name,
            models.Product.brand,
            models.Product.review_score,
            models.Product.review_count
        ).filter(
            models.Product.review_score >= 4.5,
            models.Product.review_count >= 10
        ).order_by(
            desc(models.Product.review_score),
            desc(models.Product.review_count)
        ).limit(10).all()

        # 리뷰 많은 상품 TOP 10
        most_reviewed_products = db.query(
            models.Product.product_name,
            models.Product.brand,
            models.Product.review_score,
            models.Product.review_count
        ).filter(
            models.Product.review_count > 0
        ).order_by(
            desc(models.Product.review_count)
        ).limit(10).all()

        return {
            "review_distribution": [
                {
                    "score": float(record.review_score),
                    "product_count": record.count
                }
                for record in review_distribution
            ],
            "review_statistics": {
                "avg_review_count": float(review_count_stats.avg_review_count) if review_count_stats.avg_review_count else 0,
                "max_review_count": review_count_stats.max_review_count if review_count_stats.max_review_count else 0,
                "min_review_count": review_count_stats.min_review_count if review_count_stats.min_review_count else 0,
                "products_with_reviews": review_count_stats.products_with_reviews,
                "total_products": review_count_stats.total_products,
                "review_coverage_rate": (review_count_stats.products_with_reviews / review_count_stats.total_products * 100) if review_count_stats.total_products > 0 else 0
            },
            "high_rated_products": [
                {
                    "product_name": record.product_name,
                    "brand": record.brand,
                    "review_score": float(record.review_score),
                    "review_count": record.review_count
                }
                for record in high_rated_products
            ],
            "most_reviewed_products": [
                {
                    "product_name": record.product_name,
                    "brand": record.brand,
                    "review_score": float(record.review_score),
                    "review_count": record.review_count
                }
                for record in most_reviewed_products
            ]
        }

    except Exception as e:
        logger.error(f"리뷰 분석 중 오류: {str(e)}")
        raise


async def get_dashboard_summary(db: Session) -> Dict:
    """대시보드용 요약 통계"""

    try:
        # 전체 통계
        total_stats = db.query(
            func.count(models.Product.id).label('total_products'),
            func.count(models.Product.id).filter(models.Product.review_count > 0).label('products_with_reviews'),
            func.count(func.distinct(models.Product.brand)).label('total_brands'),
            func.count(func.distinct(models.Product.category)).label('total_categories')
        ).first()

        # 가격 이력 통계
        price_stats = db.query(
            func.count(models.PriceHistory.id).label('total_price_records'),
            func.avg(models.PriceHistory.sale_price).label('avg_sale_price'),
            func.avg(models.PriceHistory.discount_rate).label('avg_discount_rate')
        ).filter(
            models.PriceHistory.sale_price > 0
        ).first()

        # 최근 24시간 크롤링 통계
        yesterday = datetime.now(KST) - timedelta(days=1)
        recent_crawling = db.query(
            func.count(models.PriceHistory.id).label('recent_records')
        ).filter(
            models.PriceHistory.crawled_at >= yesterday
        ).first()

        # 인기 브랜드 TOP 5
        top_brands = db.query(
            models.Product.brand,
            func.count(models.Product.id).label('product_count')
        ).filter(
            models.Product.brand.isnot(None),
            models.Product.brand != ''
        ).group_by(
            models.Product.brand
        ).order_by(
            desc('product_count')
        ).limit(5).all()

        return {
            "overview": {
                "total_products": total_stats.total_products,
                "products_with_reviews": total_stats.products_with_reviews,
                "total_brands": total_stats.total_brands,
                "total_categories": total_stats.total_categories,
                "review_coverage_rate": (total_stats.products_with_reviews / total_stats.total_products * 100) if total_stats.total_products > 0 else 0
            },
            "pricing": {
                "total_price_records": price_stats.total_price_records,
                "avg_sale_price": int(price_stats.avg_sale_price) if price_stats.avg_sale_price else 0,
                "avg_discount_rate": float(price_stats.avg_discount_rate) if price_stats.avg_discount_rate else 0
            },
            "recent_activity": {
                "records_last_24h": recent_crawling.recent_records
            },
            "top_brands": [
                {
                    "brand": record.brand,
                    "product_count": record.product_count
                }
                for record in top_brands
            ]
        }

    except Exception as e:
        logger.error(f"대시보드 요약 통계 중 오류: {str(e)}")
        raise