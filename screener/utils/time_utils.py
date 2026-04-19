import datetime
from typing import Optional

_trade_dates: Optional[set] = None
_trade_dates_loaded: bool = False
_data_max_date: Optional[datetime.date] = None


def _load_trade_dates():
    global _trade_dates, _trade_dates_loaded, _data_max_date
    if _trade_dates_loaded:
        return
    _trade_dates_loaded = True
    _trade_dates = set()
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        for td in df["trade_date"]:
            if isinstance(td, str):
                d = datetime.datetime.strptime(td, "%Y-%m-%d").date()
            else:
                d = td.date()
            _trade_dates.add(d)
        _data_max_date = max(_trade_dates) if _trade_dates else None
    except Exception:
        pass


def is_market_open() -> bool:
    _load_trade_dates()
    now = datetime.datetime.now()
    today = now.date()
    if now.weekday() >= 5:
        return False
    if _trade_dates is not None and _data_max_date is not None and today <= _data_max_date:
        if today not in _trade_dates:
            return False
    if (now.hour == 9 and now.minute >= 30) or (10 <= now.hour < 11) or (now.hour == 11 and now.minute <= 30):
        return True
    if 13 <= now.hour < 15:
        return True
    return False


def is_trading_day() -> bool:
    _load_trade_dates()
    now = datetime.datetime.now()
    today = now.date()
    if now.weekday() >= 5:
        return False
    if _trade_dates is not None and _data_max_date is not None and today <= _data_max_date:
        if today not in _trade_dates:
            return False
    return True


def should_use_today_data() -> bool:
    now = datetime.datetime.now()
    today = now.date()
    if now.weekday() >= 5:
        return False
    if _trade_dates is not None and _data_max_date is not None and today <= _data_max_date:
        if today not in _trade_dates:
            return False
    if now.hour >= 15:
        return True
    return False
