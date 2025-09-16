from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import List


# 가격 이력 관련 스키마

class PriceHistoryBase(BaseModel):
    """가격 이력의 기본 필드를 정의하는 스키마"""
    price: float
    discount_price: float
    is_sold_out: bool

class PriceHistoryCreate(PriceHistoryBase):
    """새로운 가격 이력을 생성할 때 사용하는 스키마"""
    pass # 추가 필드 없이 PriceHistoryBase의 모든 필드를 상속받아 사용

class PriceHistory(PriceHistoryBase):
    """API 응답으로 가격 이력 정보를 반환할 때 사용하는 스키마"""
    id: int
    crawled_at: datetime

    class Config:
        # SQLAlchemy 모델 객체를 Pydantic 스키마로 자동으로 변환해주는 설정
        from_attributes = True


#  상품 관련 스키마 
class ProductBase(BaseModel):
    """상품의 기본 필드를 정의하는 스키마"""
    product_url: HttpUrl

class ProductCreate(ProductBase):
    """새로운 상품을 등록 할 때 사용하는 스키마"""
    pass # 추가 필드 없이 ProductBase의 필드를 상속받아 사용

class Product(ProductBase):
    """API 응답으로 특정 상품의 상세 정보를 반환할 때 사용하는 스키마"""
    id: int
    create_at: datetime
    # 해당 상품에 연결된 모든 가격 이력들을 리스트 형태로 포함
    price_history: List[PriceHistory] = []

    class Config:
        from_attributes = True
