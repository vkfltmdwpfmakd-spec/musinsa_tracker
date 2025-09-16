from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import pytz
from .database import Base


KST = pytz.timezone('Asia/Seoul')


class Product(Base):
    """상품 정보를 저장하는 'products' 테이블"""
    __tablename__ = "products"
    __table_args__ = {
        'comment': '무신사 상품 정보를 저장하는 테이블'
    }

    id = Column(Integer, primary_key=True, index=True, comment='상품 고유 ID')
    product_name = Column(String, index=True, comment='상품명')
    goods_no = Column(Integer, nullable=True, comment='무신사 상품번호')
    style_no = Column(String, nullable=True, comment='스타일번호')
    brand = Column(String, comment='브랜드명')
    brand_english = Column(String, nullable=True, comment='브랜드 영문명')
    category = Column(String, comment='전체 카테고리 (depth1 > depth2 > depth3)')
    category_depth1 = Column(String, nullable=True, comment='카테고리 1단계')
    category_depth2 = Column(String, nullable=True, comment='카테고리 2단계')
    category_depth3 = Column(String, nullable=True, comment='카테고리 3단계')
    product_url = Column(String, unique=True, index=True, comment='상품 페이지 URL')
    image_url = Column(String, comment='상품 이미지 URL')
    normal_price = Column(Float, nullable=True, comment='정가')
    sale_price = Column(Float, nullable=True, comment='판매가')
    discount_rate = Column(Float, default=0.0, comment='할인율 (%)')
    is_sale = Column(Boolean, default=False, comment='할인 여부')
    review_count = Column(Integer, default=0, comment='리뷰 개수')
    review_score = Column(Float, default=0.0, comment='리뷰 점수 (평균)')
    delivery_info = Column(String, nullable=True, comment='배송 정보')
    courier_name = Column(String, nullable=True, comment='택배사명')
    gender = Column(String, nullable=True, comment='성별 (M/F/공용)')
    is_sold_out = Column(Boolean, default=False, comment='품절 여부')
    stock_status = Column(String, nullable=True, comment='재고 상태 문자열')
    original_price = Column(Float, comment='정가 (기존 호환성 유지)')
    is_active = Column(Boolean, default=True, comment='가격 추적 활성화 여부')
    create_at = Column(DateTime, default=lambda: datetime.now(KST).replace(tzinfo=None), comment='상품 정보 최초 등록 시간 (KST)')

    price_history = relationship("PriceHistory", back_populates="product")

class PriceHistory(Base):
    """가격 변동 이력을 저장하는 'price_history' 테이블"""
    __tablename__ = "price_history"
    __table_args__ = {
        'comment': '상품 가격 변동 이력을 저장하는 테이블'
    }

    id = Column(Integer, primary_key=True, index=True, comment='가격 이력 고유 ID')
    product_id = Column(Integer, ForeignKey("products.id"), comment='products 테이블의 id를 참조하는 외래 키')
    price = Column(Float, comment='현재 판매가')
    discount_price = Column(Float, comment='할인가 (현재는 판매가와 동일하게 저장)')
    discount_rate = Column(Float, comment='할인율 (%)')
    stock_status = Column(String, comment='재고 상태 문자열 (예: 판매중, 품절)')
    is_sold_out = Column(Boolean, default=False, comment='품절 여부 (True/False)')
    crawled_at = Column(DateTime, default=lambda: datetime.now(KST).replace(tzinfo=None), comment='크롤링 실행 시간 (KST)')

    product = relationship("Product", back_populates="price_history")
