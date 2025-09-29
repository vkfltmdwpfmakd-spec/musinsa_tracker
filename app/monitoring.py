from prometheus_client import Counter, Histogram, Gauge, Info
import psutil
import time
from functools import wraps

# 크롤링 관련 메트릭
crawling_requests_total = Counter(
    'musinsa_crawling_requests_total',
    'Total crawling requests',
    ['category', 'status']
)

crawling_duration_seconds = Histogram(
    'musinsa_crawling_duration_seconds',
    'Time spent on crawling',
    ['category']
)

crawling_products_total = Counter(
    'musinsa_crawling_products_total',
    'Total products crawled',
    ['category']
)

review_collection_success = Counter(
    'musinsa_review_collection_success_total',
    'Successful review collections',
    ['category']
)

# 시스템 메트릭
system_cpu_usage = Gauge('musinsa_system_cpu_usage_percent', 'System CPU usage')
system_memory_usage = Gauge('musinsa_system_memory_usage_percent', 'System memory usage')
system_disk_usage = Gauge('musinsa_system_disk_usage_percent', 'System disk usage')

# 데이터베이스 메트릭
db_products_total = Gauge('musinsa_db_products_total', 'Total products in database')
db_products_with_reviews = Gauge('musinsa_db_products_with_reviews', 'Products with reviews in database')

# API 정보
api_info = Info('musinsa_api_info', 'Musinsa API information')
api_info.info({
    'version': '1.0.0',
    'description': 'Musinsa Price Tracker API',
    'python_version': '3.10'
})

def track_crawling_metrics(category: str):
    """크롤링 메트릭을 추적하는 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                # 성공 메트릭
                crawling_requests_total.labels(category=category, status='success').inc()

                # 수집된 상품 수
                if isinstance(result, dict) and 'total_saved' in result:
                    crawling_products_total.labels(category=category).inc(result['total_saved'])

                return result

            except Exception as e:
                # 실패 메트릭
                crawling_requests_total.labels(category=category, status='error').inc()
                raise

            finally:
                # 실행 시간
                duration = time.time() - start_time
                crawling_duration_seconds.labels(category=category).observe(duration)

        return wrapper
    return decorator

def update_system_metrics():
    """시스템 메트릭 업데이트"""
    # CPU 사용률
    cpu_percent = psutil.cpu_percent(interval=1)
    system_cpu_usage.set(cpu_percent)

    # 메모리 사용률
    memory = psutil.virtual_memory()
    system_memory_usage.set(memory.percent)

    # 디스크 사용률
    disk = psutil.disk_usage('/')
    disk_percent = (disk.used / disk.total) * 100
    system_disk_usage.set(disk_percent)

def update_database_metrics(db_session):
    """데이터베이스 메트릭 업데이트"""
    from .models import Product

    # 총 상품 수
    total_products = db_session.query(Product).count()
    db_products_total.set(total_products)

    # 리뷰 있는 상품 수
    products_with_reviews = db_session.query(Product).filter(Product.review_count > 0).count()
    db_products_with_reviews.set(products_with_reviews)

