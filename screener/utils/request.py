import time
import random
import logging
import functools

logger = logging.getLogger("justice")

def rate_limit(min_sec: float = 0.5, max_sec: float = 1.5):
    """随机延迟，避免被封控"""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            time.sleep(random.uniform(min_sec, max_sec))
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def retry_with_backoff(max_retries: int = 3, backoff_base: float = 2.0, exceptions=(Exception,)):
    """
    指数退避重试装饰器
    第1次失败等 backoff_base^1 秒，第2次等 backoff_base^2 秒，以此类推
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    wait = (backoff_base ** (attempt + 1)) + random.uniform(0, 1)
                    logger.warning(
                        f"{fn.__name__} 第{attempt+1}次失败: {e}，{wait:.1f}s 后重试"
                    )
                    time.sleep(wait)
            raise last_exc
        return wrapper
    return decorator

def random_headers() -> dict:
    """返回随机 User-Agent，模拟正常浏览器行为"""
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(agents),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
