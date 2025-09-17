import asyncio
from playwright.async_api import async_playwright
import argparse

# docker-compose exec api python app/musinsa_category_analyzer.py https://www.musinsa.com/categories/item/002

async def main():
    parser = argparse.ArgumentParser(description="무신사 카테고리 페이지의 DOM 구조를 분석하는 스크립트")

    parser.add_argument('url', type=str, help='분석할 무신사 카테고리 페이지 URL')

    args = parser.parse_args()

    print(f"페이지로 이동 중: {args.url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        try:
            await page.goto(args.url, wait_until="networkidle", timeout=60000)

            # 페이지의 최종 HTML 컨텐츠를 가져옴 (js 실행 완료 후)
            content = await page.content()

            file_path = "/code/app/musinsa_category_content.html"

            # HTML 저장
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"성공: 페이지의 HTML을 다음 경로에 저장했습니다: {file_path}")

            # DOM 구조 분석
            print("\n=== 상품 컨테이너 찾기 ===")

            selectors = [
                ".list-box",
                ".goods-item",
                ".product-item",
                ".item",
                "[data-goods-no]",
                ".li_box",
                ".box",
                ".list-item",
                "li"
            ]

            for selector in selectors:
                elements = await page.query_selector_all(selector)
                print(f"'{selector}': {len(elements)}개 발견")

                if elements and len(elements) > 20:  # 상품이 많이 있는 셀렉터
                    print(f"  >> '{selector}'가 상품 컨테이너일 가능성 높음")

                    # 첫 번째 상품의 구조 분석
                    first = elements[0]

                    # 링크 찾기
                    links = await first.query_selector_all("a")
                    if links:
                        href = await links[0].get_attribute("href")
                        print(f"  - 상품 링크: {href}")

                    # 이미지 찾기
                    images = await first.query_selector_all("img")
                    if images:
                        src = await images[0].get_attribute("src")
                        alt = await images[0].get_attribute("alt")
                        print(f"  - 이미지: {src}")
                        print(f"  - 이미지 alt: {alt}")

                    print("  - 내부 HTML 구조:")
                    inner_html = await first.inner_html()
                    print(f"    {inner_html[:200]}...")

                    break

        except Exception as e:
            print(f"오류 발생: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())