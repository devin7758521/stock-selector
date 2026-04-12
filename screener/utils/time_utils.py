import datetime

def is_market_open() -> bool:
    """判断当前是否是A股开市时间"""
    now = datetime.datetime.now()
    # 周一到周五
    if now.weekday() >= 5:
        return False
    # 上午 9:30-11:30
    if (9 <= now.hour < 11) or (now.hour == 11 and now.minute <= 30):
        return True
    # 下午 13:00-15:00
    if 13 <= now.hour < 15:
        return True
    return False

def is_trading_day() -> bool:
    """判断当前是否是交易日"""
    now = datetime.datetime.now()
    # 周一到周五
    if now.weekday() >= 5:
        return False
    return True

def should_use_today_data() -> bool:
    """判断是否应该使用当天的数据"""
    now = datetime.datetime.now()
    # 周一到周五
    if now.weekday() >= 5:
        return False
    # 下午三点以后，使用当天的日K数据
    if now.hour >= 15:
        return True
    return False
