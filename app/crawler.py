import asyncio
import logging
import json
import re
from playwright.async_api import async_playwright
from typing import Optional, Dict, Any


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_discount_rate(original_price: float, discount_price: float) -> float:
    """정가와 할인가를 바탕으로 할인율(%)을 계산"""
    if original_price <= 0 or original_price < discount_price:
        return 0.0

    return round(((original_price - discount_price) / original_price) * 100, 2)


async def extract_data_from_script_tag(page) -> Optional[Dict[str, Any]]:
    """페이지의 <script> 태그에 포함된 JSON 데이터를 파싱하여 상품 정보를 추출"""
    try:
        # 페이지의 모든 <script> 태그를 가져오기
        scripts = await page.query_selector_all("script")
        for script in scripts:
            content = await script.inner_text()
            # 상품 정보가 포함된 `window.__MSS_FE__.product.state` 객체를 찾기
            if "window.__MSS_FE__" in content and "product.state" in content:
                # 정규식을 사용하여 스크립트 내용에서 JSON 부분 추출
                match = re.search(r'window\.__MSS_FE__\.product\.state = (\{.*?\});', content, re.DOTALL)
                if match:
                    json_text = match.group(1)
                    data = json.loads(json_text)

                    # 기본 상품 정보 추출
                    product_name = data.get("goodsNm")
                    goods_no = data.get("goodsNo")
                    style_no = data.get("styleNo")

                    # 브랜드 정보 추출
                    brand_info = data.get("brandInfo", {})
                    brand = brand_info.get("brandName")
                    brand_english = brand_info.get("brandEnglishName")

                    # 이미지 정보 추출
                    image_url = data.get("thumbnailImageUrl")

                    # 가격 정보 추출
                    price_info = data.get("goodsPrice", {})
                    normal_price = float(price_info.get("normalPrice", 0))  # 정가
                    sale_price = float(price_info.get("salePrice", 0))      # 판매가
                    discount_rate = price_info.get("discountRate", 0)       # 할인율
                    is_sale = price_info.get("isSale", False)               # 할인 여부

                    # 카테고리 정보 추출
                    category_info = data.get("category", {})
                    category_depth1 = category_info.get("categoryDepth1Name", "")
                    category_depth2 = category_info.get("categoryDepth2Name", "")
                    category_depth3 = category_info.get("categoryDepth3Name", "")
                    category_full = f"{category_depth1} > {category_depth2} > {category_depth3}".strip(" > ")

                    # 재고 및 판매 상태 추출
                    out_of_stock = data.get("outOfStock", False)
                    is_sold_out = data.get("isSoldOut", out_of_stock)
                    
                    # 리뷰 정보 추출
                    review_info = data.get("goodsReview", {})
                    review_count = review_info.get("totalCount", 0)
                    review_score = review_info.get("satisfactionScore", 0)

                    # 배송 정보 추출
                    logistics_info = data.get("goodsLogisticsInfo", {})
                    delivery_info = logistics_info.get("deliveryInfoName", "")
                    courier_name = logistics_info.get("courierName", "")

                    # 성별 정보 추출
                    genders = data.get("genders", [])
                    gender = "/".join(genders) if genders else "공용"

                    # 필수 정보들이 모두 추출되었는지 확인
                    if product_name and brand and image_url:
                        logger.info("성공: Script 태그의 JSON 데이터에서 핵심 정보를 추출했습니다.")

                        # 이미지 URL이 상대 경로인 경우, 완전한 URL로 만들기
                        if image_url.startswith("//"):
                            image_url = "https:" + image_url
                        elif image_url.startswith("/"):
                            image_url = "https://image.msscdn.net" + image_url

                        # 추출한 데이터를 딕셔너리 형태로 반환
                        return {
                            "product_name": product_name,
                            "goods_no": goods_no,
                            "style_no": style_no,
                            "brand": brand,
                            "brand_english": brand_english,
                            "category": category_full,
                            "category_depth1": category_depth1,
                            "category_depth2": category_depth2,
                            "category_depth3": category_depth3,
                            "image_url": image_url,
                            "normal_price": normal_price,
                            "sale_price": sale_price,
                            "discount_rate": discount_rate,
                            "is_sale": is_sale,
                            "is_sold_out": is_sold_out,
                            "review_count": review_count,
                            "review_score": review_score,
                            "delivery_info": delivery_info,
                            "courier_name": courier_name,
                            "gender": gender
                        }
    except Exception as e:
        logger.warning(f"오류: Script 태그 JSON 파싱 중 문제가 발생했습니다: {e}")

    logger.warning("실패: Script 태그에서 데이터를 추출하지 못했습니다.")
    return None


async def fetch_product_data(url: str) -> Optional[Dict[str, Any]]:
    """주어진 URL의 상품 페이지에 접속하여 상품 데이터를 크롤링합니다."""
    logger.info(f"크롤링 시작: {url}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            logger.info("페이지 로드 완료")

            # script 태그에 숨겨진 JSON 데이터에서 정보 추출
            json_data = await extract_data_from_script_tag(page)

            # JSON 데이터 추출에 실패 시 크롤링 중단
            if not json_data:
                logger.error("JSON 데이터에서 상품 정보를 추출할 수 없어 크롤링을 중단합니다.")
                await browser.close()
                return None

            # 추출한 데이터를 각 변수에 할당
            product_name = json_data.get("product_name")
            goods_no = json_data.get("goods_no")
            style_no = json_data.get("style_no")
            brand = json_data.get("brand")
            brand_english = json_data.get("brand_english")
            category = json_data.get("category")
            category_depth1 = json_data.get("category_depth1")
            category_depth2 = json_data.get("category_depth2")
            category_depth3 = json_data.get("category_depth3")
            image_url = json_data.get("image_url")
            normal_price = json_data.get("normal_price", 0.0)
            sale_price = json_data.get("sale_price", 0.0)
            discount_rate = json_data.get("discount_rate", 0.0)
            is_sale = json_data.get("is_sale", False)
            is_sold_out = json_data.get("is_sold_out", False)
            review_count = json_data.get("review_count", 0)
            review_score = json_data.get("review_score", 0.0)
            delivery_info = json_data.get("delivery_info")
            courier_name = json_data.get("courier_name")
            gender = json_data.get("gender")

            # 재고 상태 문자열 생성
            stock_status = "품절" if is_sold_out else "판매중"

            await browser.close()
            logger.info("크롤링 완료")

            # 최종 결과를 딕셔너리 형태로 정리 (확장된 데이터 포함)
            result = {
                "product_name": product_name,
                "goods_no": goods_no,
                "style_no": style_no,
                "brand": brand or "알 수 없음",
                "brand_english": brand_english or "",
                "category": category or "기타",
                "category_depth1": category_depth1 or "",
                "category_depth2": category_depth2 or "",
                "category_depth3": category_depth3 or "",
                "product_url": url,
                "image_url": image_url,
                "normal_price": normal_price,
                "sale_price": sale_price,
                "discount_rate": discount_rate,
                "is_sale": is_sale,
                "stock_status": stock_status,
                "is_sold_out": is_sold_out,
                "review_count": review_count,
                "review_score": review_score,
                "delivery_info": delivery_info or "",
                "courier_name": courier_name or "",
                "gender": gender or "공용",
                "is_active": True  # 추적 활성화 상태 (기본값 True)
            }
            logger.info(f"크롤링 결과: {result}")
            return result

        except Exception as e:
            logger.error(f"크롤링 중 심각한 오류 발생: {e}")
            if not page.is_closed():
                await browser.close()
            return None


if __name__ == "__main__":
    test_url = "https://www.musinsa.com/products/5394845"
    data = asyncio.run(fetch_product_data(test_url))
    
    if data:
        print(json.dumps(data, ensure_ascii=False, indent=4))
