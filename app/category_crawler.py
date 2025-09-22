import asyncio
import logging
import json
import time
import re
from playwright.async_api import async_playwright
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MUSINSA_CATEGORIES = {
    "상의": "001",
    "아우터": "002",
    "하의": "003",
    "신발": "022",
    "가방": "025",
    "모자": "007",
    "양말": "008",
    "언더웨어": "009",
    "악세서리": "010"
}


def parse_price_from_text(price_text: str) -> tuple[int, int, float]:
    """
    가격 텍스트에서 정가, 판매가, 할인율 추출
    반환: (정가, 판매가, 할인율)
    """
    if not price_text or price_text.strip() == "0":
        return 0, 0, 0.0

    # 모든 숫자 추출 (쉼표 포함)
    price_numbers = re.findall(r'[\d,]+', price_text)

    if not price_numbers:
        return 0, 0, 0.0

    # 쉼표 제거하고 정수 변환
    prices = [int(num.replace(',', '')) for num in price_numbers]

    if len(prices) == 1:
        # 가격이 하나만 있는 경우 (할인 없음)
        return prices[0], prices[0], 0.0
    elif len(prices) >= 2:
        # 여러 가격이 있는 경우 (첫 번째가 높으면 정가, 두 번째가 판매가)
        original = max(prices)
        sale = min(prices)

        if original > sale:
            discount_rate = round((original - sale) / original * 100, 1)
            return original, sale, discount_rate
        else:
            return sale, sale, 0.0

    return 0, 0, 0.0


async def fetch_category_products(category_code: str, target_count: int = 300) -> List[Dict]:
    """카테고리에서 상품 목록 수집 (스크롤 방식)"""

    products = []
    logger.info(f"카테고리 코드: {category_code} - 크롤링 시작 (목표: {target_count}개)")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # User agent 설정하여 봇 감지 우회
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        try:
            # 기본 카테고리 페이지 로드 
            url = f"https://www.musinsa.com/category/{category_code}?d_cat_cd={category_code}&brand=&list_kind=small&sort=pop"
            logger.info(f"카테고리 페이지 로드: {url}")

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # 상품 컨테이너가 로드될 때까지 기다리기
            try:
                await page.wait_for_selector('div.sc-ibashp', timeout=10000)
                logger.info("상품 컨테이너 로드 확인됨")
            except:
                logger.warning("상품 컨테이너를 찾을 수 없습니다.")
                return products

            # 초기 로드 대기
            await page.wait_for_timeout(3000)

            # 스크롤하면서 상품 수집
            scroll_count = 0
            max_scrolls = 10  # 최대 스크롤 횟수
            processed_urls = set()  # 중복 제거용

            while len(products) < target_count and scroll_count < max_scrolls:
                # 현재 페이지의 모든 상품 링크 직접 수집
                product_links = await page.query_selector_all("a.gtm-select-item")
                logger.info(f"스크롤 {scroll_count}: {len(product_links)}개 상품 발견")

                # 상품 정보 추출
                for link_element in product_links:
                    try:
                        if not link_element:
                            continue

                        # URL 추출
                        href = await link_element.get_attribute("href")
                        if not href:
                            continue
                        product_url = f"https://www.musinsa.com{href}" if href.startswith("/") else href

                        # data 속성에서 정보 추출
                        brand = await link_element.get_attribute("data-brand-id") or "Unknown"
                        brand_english = await link_element.get_attribute("data-item-brand") or None
                        goods_no = int(await link_element.get_attribute("data-item-id") or "0")
                        sale_price = int(await link_element.get_attribute("data-price") or "0")
                        original_price = int(await link_element.get_attribute("data-original-price") or "0")
                        discount_rate = int(await link_element.get_attribute("data-discount-rate") or "0")

                        # 원가가 없는 경우 판매가와 할인율로 계산
                        if original_price == 0 and discount_rate > 0 and sale_price > 0:
                            original_price = int(sale_price / (1 - discount_rate / 100))
                        elif original_price == 0:
                            original_price = sale_price

                        # 상품명과 이미지 URL 추출
                        img_element = await link_element.query_selector("img")
                        product_name = await img_element.get_attribute("alt") if img_element else "Unknown"
                        image_url = await img_element.get_attribute("src") if img_element else None

                        # 리뷰 정보 크롤링
                        review_count = 0
                        review_score = 0.0

                        try:
                            # 리뷰 개수 (괄호 있는 요소)
                            review_count_element = await link_element.query_selector("span.text-etc_11px_reg.text-yellow.font-pretendard")
                            if review_count_element:
                                review_text = await review_count_element.text_content()
                                if review_text and "(" in review_text:
                                    # "(1,234)" 형태에서 숫자 추출
                                    import re
                                    count_match = re.search(r'\(([0-9,]+)\)', review_text)
                                    if count_match:
                                        review_count = int(count_match.group(1).replace(',', ''))
                                elif review_text and "(" not in review_text:
                                    # 평점 (괄호 없는 요소)
                                    try:
                                        review_score = float(review_text.strip())
                                    except:
                                        pass
                        except Exception as e:
                            logger.debug(f"리뷰 정보 추출 실패: {e}")

                        # 카테고리명 추가
                        category_name = None
                        for name, code in MUSINSA_CATEGORIES.items():
                            if code == category_code:
                                category_name = name
                                break

                        # 디버깅용 가격 텍스트
                        price_text = f"판매가: {sale_price}원, 원가: {original_price}원, 할인율: {discount_rate}%"

                        product_data = {
                            "product_url": product_url,
                            "product_name": product_name,
                            "goods_no": goods_no,
                            "brand": brand,
                            "brand_english": brand_english,
                            "category": category_name,
                            "category_code": category_code,
                            "normal_price": original_price,
                            "sale_price": sale_price,
                            "discount_rate": discount_rate,
                            "price_text": price_text,  # 디버깅용
                            "image_url": image_url,
                            "review_count": review_count,
                            "review_score": review_score,
                            "is_sold_out": False
                        }

                        # 중복 제거 (URL로 체크)
                        if product_url not in processed_urls:
                            processed_urls.add(product_url)
                            products.append(product_data)

                            # 첫 3개 상품만 디버깅 정보 출력 -- 삭제 예정
                            if len(products) <= 10:
                                logger.info(f"=== {len(products)}번째 상품 ===")
                                logger.info(f"상품명: {product_data['product_name']}")
                                logger.info(f"브랜드: {product_data['brand']}")
                                logger.info(f"원가격: {product_data['normal_price']}원")
                                logger.info(f"판매가: {product_data['sale_price']}원")
                                logger.info(f"할인율: {product_data['discount_rate']}%")
                                logger.info(f"가격 텍스트: {product_data['price_text']}")
                                logger.info(f"상품 URL: {product_data['product_url']}")
                                logger.info(f"이미지 URL: {product_data['image_url']}")
                                logger.info("=" * 30)

                            # 목표 개수 달성 시 조기 종료
                            if len(products) >= target_count:
                                logger.info(f"목표 상품 수 달성: {len(products)}개")
                                break

                    except Exception as e:
                        logger.warning(f"상품 정보 추출 중 오류 발생: {e}")
                        continue

                # 목표 달성 시 루프 탈출
                if len(products) >= target_count:
                    break

                # 스크롤 실행
                scroll_count += 1
                logger.info(f"스크롤 {scroll_count} 실행 - 현재 {len(products)}개 상품 수집")

                # 페이지 끝까지 스크롤
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)  # 새로운 상품 로드 대기

            logger.info(f"카테고리 {category_code} 크롤링 완료 - 총 {len(products)}개 상품 수집")

        except Exception as e:
            logger.error(f"카테고리 {category_code} - 크롤링 중 오류 발생: {e}")

        finally:
            await browser.close()

    return products



async def fetch_multiple_categories(categories: List[str], target_count: int = 300) -> Dict[str, List[Dict]]:
    """여러 카테고리 상품 동시 수집"""
    results = {}

    for category_code in categories:
        products = await fetch_category_products(category_code, target_count)
        results[category_code] = products

        # 카테고리 간 딜레이
        await asyncio.sleep(2)

    return results



if __name__ == "__main__":
    # 테스트용으로 소량 수집
    test_products = asyncio.run(fetch_category_products("002", target_count=10))

    print(f"\n수집된 상품 수 : {len(test_products)}개")

    for i,product in enumerate(test_products[:10]):
        print(f"{i+1}. {product['product_name']}")
        print(f"    URL: {product['product_url']}")
        print(f"   브랜드: {product['brand']}")
        print(f"   가격: {product['price_text']}")

