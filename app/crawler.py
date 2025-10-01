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
            # 상품 정보가 포함된 `window.__MSS__.product.state` 객체를 찾기
            if "window.__MSS__" in content and "product.state" in content:
                # 중괄호 매칭으로 완전한 JSON 객체 추출
                start_pattern = 'window.__MSS__.product.state = '
                start_idx = content.find(start_pattern)
                if start_idx != -1:
                    start_idx += len(start_pattern)

                    # 중괄호 매칭으로 완전한 JSON 객체 추출
                    brace_count = 0
                    json_start = start_idx
                    json_end = json_start

                    for i, char in enumerate(content[json_start:], json_start):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                json_end = i + 1
                                break

                    if brace_count == 0:
                        json_text = content[json_start:json_end]
                        try:
                            data = json.loads(json_text)

                            # 기본 상품 정보 추출
                            product_name = data.get("goodsNm")
                            goods_no = data.get("goodsNo")
                            style_no = data.get("styleNo")

                            # 브랜드 정보 추출
                            brand_info = data.get("brandInfo", {})
                            if brand_info is None:
                                brand_info = {}
                            brand = brand_info.get("brandName")
                            brand_english = brand_info.get("brandEnglishName")

                            # 이미지 정보 추출
                            image_url = data.get("thumbnailImageUrl")

                            # 가격 정보 추출
                            price_info = data.get("goodsPrice", {})
                            if price_info is None:
                                price_info = {}
                            normal_price = float(price_info.get("normalPrice", 0))  # 정가
                            sale_price = float(price_info.get("salePrice", 0))      # 판매가
                            discount_rate = price_info.get("discountRate", 0)       # 할인율
                            is_sale = price_info.get("isSale", False)               # 할인 여부

                            # 카테고리 정보 추출
                            category_info = data.get("category", {})
                            if category_info is None:
                                category_info = {}

                            # 카테고리 이름 추출
                            category_depth1 = category_info.get("categoryDepth1Name", "")
                            category_depth2 = category_info.get("categoryDepth2Name", "")
                            category_depth3 = category_info.get("categoryDepth3Name", "")

                            # 카테고리 코드 추출
                            category_depth1_code = category_info.get("categoryDepth1Code", "")
                            category_depth2_code = category_info.get("categoryDepth2Code", "")
                            category_depth3_code = category_info.get("categoryDepth3Code", "")

                            category_full = f"{category_depth1} > {category_depth2} > {category_depth3}".strip(" > ")

                            # 재고 및 판매 상태 추출
                            out_of_stock = data.get("outOfStock", False)
                            is_sold_out = data.get("isSoldOut", out_of_stock)

                            # 리뷰 정보 추출
                            review_info = data.get("goodsReview", {})
                            if review_info is None:
                                review_info = {}
                            review_count = review_info.get("totalCount", 0)
                            review_score = review_info.get("satisfactionScore", 0)

                            # 배송 정보 추출
                            logistics_info = data.get("goodsLogisticsInfo", {})
                            if logistics_info is None:
                                logistics_info = {}
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

                                # 추출한 데이터를 딕셔너리 형태로 반환 (가격정보는 별도 처리)
                                return {
                                    "product_name": product_name,
                                    "goods_no": goods_no,
                                    "brand": brand,
                                    "brand_english": brand_english,
                                    "category": category_depth2 if category_depth2 else category_depth1,  # 2단계 우선, 없으면 1단계
                                    "category_depth1": category_depth1,
                                    "category_depth1_code": category_depth1_code,
                                    "category_depth2": category_depth2,
                                    "category_depth2_code": category_depth2_code,
                                    "category_depth3": category_depth3,
                                    "category_depth3_code": category_depth3_code,
                                    "image_url": image_url,
                                    "review_count": review_count,
                                    "review_score": review_score,
                                    # 가격 정보는 price_history 테이블용
                                    "normal_price": normal_price,
                                    "sale_price": sale_price,
                                    "discount_rate": discount_rate,
                                    "is_sale": is_sale,
                                    "is_sold_out": is_sold_out
                                }
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON 파싱 오류: {e}")
                            continue
                break  # 성공적으로 데이터를 찾았으므로 script 루프 종료
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
            brand = json_data.get("brand")
            brand_english = json_data.get("brand_english")
            category = json_data.get("category")
            category_depth1 = json_data.get("category_depth1", "")
            category_depth1_code = json_data.get("category_depth1_code", "")
            category_depth2 = json_data.get("category_depth2", "")
            category_depth2_code = json_data.get("category_depth2_code", "")
            category_depth3 = json_data.get("category_depth3", "")
            category_depth3_code = json_data.get("category_depth3_code", "")
            image_url = json_data.get("image_url")
            normal_price = json_data.get("normal_price", 0.0)
            sale_price = json_data.get("sale_price", 0.0)
            discount_rate = json_data.get("discount_rate", 0.0)
            is_sale = json_data.get("is_sale", False)
            is_sold_out = json_data.get("is_sold_out", False)
            review_count = json_data.get("review_count", 0)
            review_score = json_data.get("review_score", 0.0)

            await browser.close()
            logger.info("크롤링 완료")

            # 최종 결과를 딕셔너리 형태로 정리 (DB schema에 맞춰)
            result = {
                # Product 테이블 필드들
                "product_name": product_name,
                "goods_no": goods_no,
                "brand": brand or "알 수 없음",
                "brand_english": brand_english,
                "category": category or "기타",
                "category_depth1": category_depth1,
                "category_depth1_code": category_depth1_code,
                "category_depth2": category_depth2,
                "category_depth2_code": category_depth2_code,
                "category_depth3": category_depth3,
                "category_depth3_code": category_depth3_code,
                "product_url": url,
                "image_url": image_url,
                "review_count": review_count,
                "review_score": review_score,
                "is_active": True,
                # Price History 테이블용 필드들
                "normal_price": normal_price,
                "sale_price": sale_price,
                "discount_rate": discount_rate,
                "is_sold_out": is_sold_out
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
