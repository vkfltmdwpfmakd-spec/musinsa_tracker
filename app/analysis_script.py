import asyncio
from playwright.async_api import async_playwright
import argparse # 터미널에서 URL을 인자로 받기 위해 사용하는 라이브러리

# docker-compose exec api python app/analysis_script.py https://www.musinsa.com/products/5394845 

async def main():
    parser = argparse.ArgumentParser(description="주어진 URL의 전체 HTML 컨텐츠를 파일로 저장하는 스크립트")

    parser.add_argument('url', type=str, help='HTML을 저장할 페이지의 전체 URL')

    args = parser.parse_args()

    print(f"페이지로 이동 중: {args.url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto(args.url, wait_until="networkidle", timeout=60000)
            
            # 페이지의 최종 HTML 컨텐츠를 가져옴 (js 실행 완료 후)
            content = await page.content()
            
            file_path = "/code/app/page_content.html"
            
            # 지정된 경로에 파일을 쓰기 모드('w')와 UTF-8 인코딩
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content) # 파일에 HTML 컨텐츠 작성
            
            print(f"성공: 페이지의 HTML을 다음 경로에 저장했습니다: {file_path}")

        except Exception as e:
            print(f"오류 발생: {e}")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())