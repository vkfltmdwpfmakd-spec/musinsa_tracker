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
    brand = Column(String, comment='브랜드명')
    brand_english = Column(String, nullable=True, comment='브랜드 영문명')
    category = Column(String, comment='카테고리명 (상의, 하의 등)')
    product_url = Column(String, unique=True, index=True, comment='상품 페이지 URL')
    image_url = Column(String, comment='상품 이미지 URL')
    review_count = Column(Integer, default=0, comment='리뷰 개수')
    review_score = Column(Float, default=0.0, comment='리뷰 점수 (평균)')
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
    normal_price = Column(Float, comment='정상가 (정가)')
    sale_price = Column(Float, comment='현재 판매가')
    discount_rate = Column(Float, comment='할인율 (%)')
    is_sold_out = Column(Boolean, default=False, comment='품절 여부 (True/False)')
    crawled_at = Column(DateTime, default=lambda: datetime.now(KST).replace(tzinfo=None), comment='크롤링 실행 시간 (KST)')

    product = relationship("Product", back_populates="price_history")
