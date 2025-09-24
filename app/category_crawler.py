import asyncio
import logging
import json
import time
import re
from playwright.async_api import async_playwright
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_musinsa_categories():
    """무신사 사이트에서 동적으로 카테고리 목록을 가져옴"""
    from playwright.async_api import async_playwright
    import re
    import time

    logger.info("무신사 카테고리 목록을 동적으로 가져오는 중...")

    # 기본 카테고리 (확실히 작동하는 것들)
    fallback_categories = {
        "상의": "001",
        "아우터": "002",
        "하의": "003"
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            # 무신사 메인 페이지에서 카테고리 추출
            await page.goto('https://www.musinsa.com', wait_until='domcontentloaded', timeout=10000)
            await page.wait_for_timeout(3000)

            discovered_categories = {}
            all_links = await page.query_selector_all('a')

            # 메인 카테고리 코드 추출 (주로 001-030, 100번대)
            for link in all_links:
                try:
                    href = await link.get_attribute('href')
                    text = await link.text_content()

                    if href and text and '/category/' in href:
                        # 카테고리 코드 추출 (001, 002, 103 등)
                        match = re.search(r'/category/([0-9]{3})(?:[^0-9]|$)', href)
                        if match:
                            code = match.group(1)
                            name = text.strip()

                            # 유효한 카테고리명 필터링
                            if (len(name) < 15 and
                                name not in ['', '무신사', 'MUSINSA', '로그인', '회원가입', '전체 보기', '더보기'] and
                                not re.search(r'[0-9]', name) and
                                '/' not in name and
                                code not in discovered_categories.values()):

                                discovered_categories[name] = code

                except:
                    continue

            await browser.close()

            # 발견된 카테고리들 검증
            logger.info(f"발견된 카테고리 후보: {len(discovered_categories)}개")

            valid_categories = {}

            # 검증 과정
            async with async_playwright() as p2:
                browser2 = await p2.chromium.launch(headless=True)
                page2 = await browser2.new_page()

                await page2.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })

                # 최대 10개까지만 검증 (시간 단축)
                test_items = list(discovered_categories.items())[:10]

                for name, code in test_items:
                    try:
                        url = f'https://www.musinsa.com/category/{code}'
                        await page2.goto(url, wait_until='domcontentloaded', timeout=6000)
                        await page2.wait_for_timeout(1000)

                        # 상품 링크 확인
                        product_links = await page2.query_selector_all('a.gtm-select-item')

                        if len(product_links) > 20:  # 20개 이상 상품이 있는 카테고리만
                            valid_categories[name] = code
                            logger.info(f"✅ {name} ({code}): {len(product_links)}개 상품")
                        else:
                            logger.debug(f"❌ {name} ({code}): {len(product_links)}개 상품 (부족)")

                    except Exception as e:
                        logger.debug(f"❌ {name} ({code}): 검증 실패")
                        continue

                await browser2.close()

            # 결과 처리
            if len(valid_categories) >= 3:
                logger.info(f"동적으로 {len(valid_categories)}개 유효한 카테고리 발견")
                return valid_categories
            else:
                logger.warning("유효한 카테고리 부족, fallback 카테고리 사용")
                return fallback_categories

    except Exception as e:
        logger.error(f"카테고리 자동 발견 실패: {e}, fallback 카테고리 사용")
        return fallback_categories


# 캐시된 카테고리 (성능 최적화용)
_cached_categories = None
_cache_timestamp = None
_cache_duration = 3600  # 1시간 캐시

async def get_cached_categories():
    """캐시된 카테고리를 반환하거나, 없으면 새로 가져옵니다."""
    global _cached_categories, _cache_timestamp
    import time

    current_time = time.time()

    # 캐시가 없거나 만료된 경우
    if (_cached_categories is None or
        _cache_timestamp is None or
        current_time - _cache_timestamp > _cache_duration):

        logger.info("카테고리 캐시 갱신 중...")
        _cached_categories = await get_musinsa_categories()
        _cache_timestamp = current_time

    return _cached_categories


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

    # 동적으로 카테고리 목록 가져오기
    musinsa_categories = await get_cached_categories()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # User agent 설정하여 봇 감지 우회
        await page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

        try:
            # 기본 카테고리 페이지 로드   https://www.musinsa.com/category/002?d_cat_cd=002&brand=&list_kind=small&sort=pop&gf=A
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
                # 현재 페이지의 모든 상품 컨테이너 수집
                product_containers = await page.query_selector_all("div.sc-itBLYH")
                logger.info(f"스크롤 {scroll_count}: {len(product_containers)}개 상품 컨테이너 발견")

                # 상품 정보 추출
                for container in product_containers:
                    try:
                        if not container:
                            continue

                        # 컨테이너 내에서 링크 요소 찾기
                        link_element = await container.query_selector("a.gtm-select-item")
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
                            yellow_spans = await container.query_selector_all("span.text-etc_11px_reg.text-yellow.font-pretendard")

                            for span in yellow_spans:
                                span_text = await span.text_content()
                                if not span_text:
                                    continue

                                span_text = span_text.strip()

                                # 평점 추출 (예: "5.0", "4.5")
                                if span_text.replace('.', '').replace(',', '').isdigit() and '.' in span_text:
                                    try:
                                        score = float(span_text.replace(',', ''))
                                        if 0.0 <= score <= 5.0:
                                            review_score = score
                                            logger.info(f"평점 발견: {score}")
                                    except ValueError:
                                        pass

                                # 리뷰 개수 추출 (예: "(1)", "(123)")
                                elif span_text.startswith('(') and span_text.endswith(')'):
                                    try:
                                        count_str = span_text[1:-1]  # 괄호 제거
                                        if count_str.replace(',', '').isdigit():
                                            review_count = int(count_str.replace(',', ''))
                                            logger.info(f"리뷰 개수 발견: {review_count}")
                                    except ValueError:
                                        pass

                        except Exception as e:
                            logger.debug(f"리뷰 정보 추출 실패: {e}")

                        # 카테고리명 추가 (동적으로 가져온 카테고리 사용)
                        category_name = None
                        for name, code in musinsa_categories.items():
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
                                logger.info(f"리뷰 개수: {product_data['review_count']}개")
                                logger.info(f"리뷰 평점: {product_data['review_score']}")
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

