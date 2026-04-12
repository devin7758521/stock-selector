import datetime

# 节假日列表（2026年）
HOLIDAYS_2026 = {
    # 元旦
    datetime.date(2026, 1, 1),
    # 春节
    datetime.date(2026, 2, 11),
    datetime.date(2026, 2, 12),
    datetime.date(2026, 2, 13),
    datetime.date(2026, 2, 14),
    datetime.date(2026, 2, 15),
    # 清明节
    datetime.date(2026, 4, 4),
    datetime.date(2026, 4, 5),
    # 劳动节
    datetime.date(2026, 5, 1),
    datetime.date(2026, 5, 2),
    datetime.date(2026, 5, 3),
    # 端午节
    datetime.date(2026, 6, 10),
    # 中秋节
    datetime.date(2026, 9, 19),
    # 国庆节
    datetime.date(2026, 10, 1),
    datetime.date(2026, 10, 2),
    datetime.date(2026, 10, 3),
    datetime.date(2026, 10, 4),
    datetime.date(2026, 10, 5),
    datetime.date(2026, 10, 6),
}

def is_market_open() -> bool:
    """判断当前是否是A股开市时间"""
    now = datetime.datetime.now()
    # 周一到周五
    if now.weekday() >= 5:
        return False
    # 节假日
    if now.date() in HOLIDAYS_2026:
        return False
    # 上午 9:30-11:30
    if (now.hour == 9 and now.minute >= 30) or (10 <= now.hour < 11) or (now.hour == 11 and now.minute <= 30):
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
    # 节假日
    if now.date() in HOLIDAYS_2026:
        return False
    return True

def should_use_today_data() -> bool:
    """判断是否应该使用当天的数据"""
    now = datetime.datetime.now()
    # 周一到周五
    if now.weekday() >= 5:
        return False
    # 节假日
    if now.date() in HOLIDAYS_2026:
        return False
    # 下午三点以后，使用当天的日K数据
    if now.hour >= 15:
        return True
    return False
