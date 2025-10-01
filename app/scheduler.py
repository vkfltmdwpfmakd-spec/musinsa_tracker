import asyncio
import logging
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import pytz
from .database import SessionLocal
from .crawler import fetch_product_data
from .category_crawler import fetch_multiple_categories, get_cached_categories, get_all_categories_with_subcategories
from . import models

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 한국 시간대
KST = pytz.timezone('Asia/Seoul')

# 스케줄러 인스턴스
scheduler = AsyncIOScheduler(timezone=KST)


async def discover_new_products():
    """카테고리 크롤링으로 새로운 상품 자동 발견 및 등록 (세부 카테고리 포함)"""
    db = SessionLocal()
    try:
        # 주요 + 세부 카테고리 모두 가져오기 (138개)
        all_categories_dict = await get_all_categories_with_subcategories()

        # 주요 카테고리와 세부 카테고리 분리
        main_categories = {}
        sub_categories = {}

        for name, code in all_categories_dict.items():
            if '|' in name:
                sub_categories[name] = code
            else:
                main_categories[name] = code

        logger.info(f"사용 가능한 카테고리: 주요 {len(main_categories)}개, 세부 {len(sub_categories)}개")

        # 전략적 카테고리 선택 (5-6개)
        selected_categories = {}

        # 1) 주요 카테고리에서 2-3개 선택 (안정성)
        main_sample_count = min(3, len(main_categories))
        if main_sample_count > 0:
            main_selected = random.sample(list(main_categories.items()), main_sample_count)
            selected_categories.update(main_selected)

        # 2) 세부 카테고리에서 2-3개 선택 (다양성)
        sub_sample_count = min(3, len(sub_categories))
        if sub_sample_count > 0:
            sub_selected = random.sample(list(sub_categories.items()), sub_sample_count)
            selected_categories.update(sub_selected)

        target_categories = list(selected_categories.values())
        selected_names = list(selected_categories.keys())

        logger.info(f"선택된 카테고리 ({len(target_categories)}개): {selected_names}")
        logger.info(f"카테고리 코드: {target_categories}")

        # services.py의 비즈니스 로직 재사용
        from .services import crawl_and_save_multiple_categories

        result = await crawl_and_save_multiple_categories(
            category_codes=target_categories,
            target_count=20,  # 카테고리당 20개씩 (세부 카테고리 포함으로 증가)
            save_to_db=True,
            db=db
        )

        logger.info(f"신규 상품 발견 완료: {result['total_saved']}개 등록, {result['total_skipped']}개 중복")

    except Exception as e:
        logger.error(f"신규 상품 발견 중 오류: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def crawl_all_active_products():
    """등록된 모든 활성 상품의 가격 정보를 크롤링"""
    db = SessionLocal()
    try:
        # services.py의 비즈니스 로직 재사용
        from .services import update_product_prices

        result = await update_product_prices(db)

        logger.info(f"가격 업데이트 완료: 성공 {result['success_count']}개, 실패 {result['error_count']}개")

    except Exception as e:
        logger.error(f"가격 업데이트 중 오류: {str(e)}")
        db.rollback()
    finally:
        db.close()


async def cleanup_old_price_history():
    """30일 이상된 가격 이력 데이터 정리"""
    db = SessionLocal()
    try:
        # 30일 전 날짜 계산
        thirty_days_ago = datetime.now(KST) - timedelta(days=30)

        # 오래된 데이터 삭제
        deleted_count = db.query(models.PriceHistory).filter(
            models.PriceHistory.crawled_at < thirty_days_ago
        ).delete()

        db.commit()
        logger.info(f"오래된 가격 이력 정리 완료: {deleted_count}개 삭제")

    except Exception as e:
        logger.error(f"가격 이력 정리 중 오류: {str(e)}")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    """스케줄러 시작"""
    try:
        # 이미 실행 중인지 확인
        if scheduler.running:
            logger.warning("스케줄러가 이미 실행 중입니다. 재시작을 건너뜁니다.")
            return

        # 기존 작업이 있다면 제거
        if scheduler.get_jobs():
            logger.info("기존 작업들을 제거합니다.")
            scheduler.remove_all_jobs()

        # 1시간마다 기존 상품 가격 업데이트
        scheduler.add_job(
            crawl_all_active_products,
            trigger=IntervalTrigger(hours=1),
            id='crawl_products_hourly',
            name='1시간마다 기존 상품 가격 업데이트',
            replace_existing=True
        )

        # 4시간마다 새로운 상품 발견 (주요+세부 카테고리 혼합)
        scheduler.add_job(
            discover_new_products,
            trigger=IntervalTrigger(hours=4),
            id='discover_new_products',
            name='4시간마다 신규 상품 자동 발견 (주요+세부 카테고리 혼합)',
            replace_existing=True
        )

        # 매일 새벽 3시에 오래된 데이터 정리
        scheduler.add_job(
            cleanup_old_price_history,
            trigger=CronTrigger(hour=3, minute=0),
            id='cleanup_old_data_daily',
            name='매일 새벽 3시 오래된 데이터 정리',
            replace_existing=True
        )

        # 스케줄러 시작
        scheduler.start()
        logger.info("스케줄러가 정상적으로 시작되었습니다")

        # 등록된 작업 목록 출력
        for job in scheduler.get_jobs():
            logger.info(f"등록된 작업: {job.name} - 다음 실행: {job.next_run_time}")

    except Exception as e:
        logger.error(f"스케줄러 시작 중 오류: {str(e)}")


def stop_scheduler():
    """스케줄러 중지"""
    try:
        scheduler.shutdown(wait=False)
        logger.info("스케줄러가 중지되었습니다")
    except Exception as e:
        logger.error(f"스케줄러 중지 중 오류: {str(e)}")


def get_scheduler_status():
    """스케줄러 상태 및 작업 목록 반환"""
    try:
        running = scheduler.running
        jobs = []

        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })

        return {
            "running": running,
            "jobs": jobs,
            "job_count": len(jobs)
        }
    except Exception as e:
        logger.error(f"스케줄러 상태 조회 중 오류: {str(e)}")
        return {
            "running": False,
            "jobs": [],
            "job_count": 0,
            "error": str(e)
        }

