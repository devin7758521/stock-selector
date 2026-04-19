import datetime
import os
import logging
from typing import Optional, Dict, Set

logger = logging.getLogger("stock_selector.time_utils")

_holidays_cache: Dict[int, Set[datetime.date]] = {}
_cache_loaded_year: Optional[int] = None
_cache_loaded_month: Optional[int] = None


def _get_cache_dir() -> str:
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cache_dir = os.path.join(base, ".cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _load_holidays_from_network(year: int) -> Optional[Set[datetime.date]]:
    try:
        import requests
        url = f"https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("days"):
            logger.debug(f"[time_utils] {year} 年数据为空，可能尚未发布")
            return None
        holidays = set()
        for day in data.get("days", []):
            d = datetime.date.fromisoformat(day["date"])
            if day.get("isOffDay", False):
                holidays.add(d)
        logger.info(f"[time_utils] 从网络加载 {year} 年节假日: {len(holidays)} 天")
        return holidays
    except Exception as e:
        logger.warning(f"[time_utils] 从网络加载节假日失败: {e}")
        return None


def _load_holidays_cached(year: int) -> Set[datetime.date]:
    now = datetime.datetime.now()
    current_year = now.year
    current_month = now.month

    global _holidays_cache, _cache_loaded_year, _cache_loaded_month

    in_january = (current_month == 1)
    same_year_loaded = (_cache_loaded_year == year and _cache_loaded_month == current_month)
    if same_year_loaded and not in_january:
        return _holidays_cache.get(year, set())

    cache_file = os.path.join(_get_cache_dir(), f"holidays_{year}.json")
    if os.path.exists(cache_file) and not in_january:
        try:
            import json
            with open(cache_file, "r") as f:
                dates = json.load(f)
            holidays = {datetime.date.fromisoformat(d) for d in dates}
            _holidays_cache[year] = holidays
            _cache_loaded_year = year
            _cache_loaded_month = current_month
            logger.info(f"[time_utils] 从缓存加载 {year} 年节假日: {len(holidays)} 天")
            return holidays
        except Exception as e:
            logger.debug(f"[time_utils] 缓存读取失败: {e}")

    holidays = _load_holidays_from_network(year)
    if holidays:
        _holidays_cache[year] = holidays
        _cache_loaded_year = year
        _cache_loaded_month = current_month
        _save_holidays_cache(year, holidays)
        return holidays

    cached = _holidays_cache.get(year)
    if cached is not None:
        return cached

    logger.debug(f"[time_utils] {year} 年节假日数据不可用，暂不检查节假日")
    return set()


def _save_holidays_cache(year: int, holidays: Set[datetime.date]):
    try:
        cache_file = os.path.join(_get_cache_dir(), f"holidays_{year}.json")
        import json
        with open(cache_file, "w") as f:
            json.dump([d.isoformat() for d in holidays], f)
    except Exception:
        pass


def is_market_open() -> bool:
    now = datetime.datetime.now()
    today = now.date()
    year = today.year

    if now.weekday() >= 5:
        return False

    holidays = _load_holidays_cached(year)
    if holidays and today in holidays:
        return False

    if (now.hour == 9 and now.minute >= 30) or (10 <= now.hour < 11) or (now.hour == 11 and now.minute <= 30):
        return True
    if 13 <= now.hour < 15:
        return True
    return False


def is_trading_day() -> bool:
    now = datetime.datetime.now()
    today = now.date()
    year = today.year

    if now.weekday() >= 5:
        return False

    holidays = _load_holidays_cached(year)
    if holidays and today in holidays:
        return False
    return True


def should_use_today_data() -> bool:
    now = datetime.datetime.now()
    today = now.date()
    year = today.year

    if now.weekday() >= 5:
        return False

    holidays = _load_holidays_cached(year)
    if holidays and today in holidays:
        return False

    if now.hour >= 15:
        return True
    return False
