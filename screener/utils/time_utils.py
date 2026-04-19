import datetime
from typing import Optional

_trade_dates: Optional[set] = None
_trade_dates_loaded: bool = False


def _load_trade_dates():
    global _trade_dates, _trade_dates_loaded
    if _trade_dates_loaded:
        return
    _trade_dates_loaded = True
    _trade_dates = set()
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        for td in df["trade_date"]:
            if isinstance(td, str):
                _trade_dates.add(datetime.datetime.strptime(td, "%Y-%m-%d").date())
            else:
                _trade_dates.add(td.date())
    except Exception:
        pass


def is_market_open() -> bool:
    _load_trade_dates()
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return False
    if _trade_dates and now.date() not in _trade_dates:
        return False
    if (now.hour == 9 and now.minute >= 30) or (10 <= now.hour < 11) or (now.hour == 11 and now.minute <= 30):
        return True
    if 13 <= now.hour < 15:
        return True
    return False


def is_trading_day() -> bool:
    _load_trade_dates()
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return False
    if _trade_dates and now.date() not in _trade_dates:
        return False
    return True


def should_use_today_data() -> bool:
    now = datetime.datetime.now()
    if now.weekday() >= 5:
        return False
    if _trade_dates and now.date() not in _trade_dates:
        return False
    if now.hour >= 15:
        return True
    return False
