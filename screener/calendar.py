"""
calendar.py
===========
A股日K → 周K 聚合 + 本周交易进度计算

核心设计：
  1. 日K按ISO自然周分组聚合为周K，残缺周（节假日）原样保留
  2. 本周进度通过 baostock 交易日历计算，不硬编码节假日
     - 本周应有交易日数 = baostock 返回本周实际交易日数（自动识别节假日）
     - 本周已完成交易日数 = 今天之前（含今天）已过的交易日数
  3. 未完成周的当周成交量按进度放大，用于量均线计算

A股节假日特殊情况举例（均能正确处理）：
  - 春节：某周只有周一周二开市（2天），节假日占周三到周五
  - 劳动节：某周只有周四周五开市（2天）
  - 调休补班：某周六开市，该周实际有6天（baostock会包含）
"""

import logging
import datetime
from typing import Tuple, Optional
import threading

import pandas as pd

logger = logging.getLogger("justice.calendar")

# ── 交易日历缓存（线程安全）────────────────────────────────
_calendar_cache: Optional[pd.Series] = None
_calendar_lock  = threading.Lock()
_cache_year: Optional[int] = None


def _load_trade_dates(year: int) -> Optional[pd.Series]:
    """从 baostock 加载指定年份的交易日历"""
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_trade_dates(
            start_date=f"{year}-01-01",
            end_date=f"{year}-12-31",
        )
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        df = pd.DataFrame(rows, columns=rs.fields)
        dates = pd.to_datetime(
            df[df["is_trading_day"] == "1"]["calendar_date"]
        ).reset_index(drop=True)
        logger.info(f"[calendar] {year}年交易日历加载: {len(dates)} 个交易日")
        return dates
    except Exception as e:
        logger.warning(f"[calendar] baostock 交易日历加载失败: {e}")
        return None


def get_trade_dates_cached(year: int) -> Optional[pd.Series]:
    """获取交易日历（带缓存，同年份只加载一次）"""
    global _calendar_cache, _cache_year
    with _calendar_lock:
        if _calendar_cache is not None and _cache_year == year:
            return _calendar_cache
        dates = _load_trade_dates(year)
        if dates is not None:
            _calendar_cache = dates
            _cache_year = year
        return dates


def get_week_trade_days(trade_dates: pd.Series, week_monday: datetime.date) -> Tuple[int, int]:
    """
    返回指定周的交易日情况：
      (total_days, completed_days)
      - total_days:     本周应有的交易日数（识别节假日后的实际值）
      - completed_days: 截至今天本周已完成的交易日数

    week_monday: 本周周一的日期
    """
    today = datetime.date.today()
    week_end = week_monday + datetime.timedelta(days=6)  # 周日

    # 本周所有交易日
    week_mask = (
        (trade_dates.dt.date >= week_monday) &
        (trade_dates.dt.date <= week_end)
    )
    week_trade_days = trade_dates[week_mask]
    total = len(week_trade_days)

    # 已完成的交易日（今天收盘前算进行中，保守取昨天及以前）
    # 下午1点运行时，今天的数据还未收盘，所以"已完成"算到昨天
    yesterday = today - datetime.timedelta(days=1)
    completed_mask = week_trade_days.dt.date <= yesterday
    completed = completed_mask.sum()

    return total, completed


# ─────────────────────────────────────────────────────────────
# 核心：日K → 周K 聚合
# ─────────────────────────────────────────────────────────────
def resample_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    日K → 周K（按ISO自然周分组）

    输入：df_daily，必须包含 date/open/high/low/close/volume/amount 列
    输出：周K DataFrame，列名相同
          额外列 _days: 该周实际交易日数（供进度计算使用，内部列）
    """
    df = df_daily.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    iso = df["date"].dt.isocalendar()
    df["_iso_year"] = iso.year.astype(int)
    df["_iso_week"] = iso.week.astype(int)
    df["_week_key"] = df["_iso_year"] * 100 + df["_iso_week"]

    rows = []
    for _, grp in df.groupby("_week_key", sort=True):
        grp = grp.sort_values("date")
        rows.append({
            "date":   grp["date"].iloc[-1],   # 该周最后一个实际交易日
            "open":   grp["open"].iloc[0],
            "high":   grp["high"].max(),
            "low":    grp["low"].min(),
            "close":  grp["close"].iloc[-1],
            "volume": grp["volume"].sum(),
            "amount": grp["amount"].sum(),
            "_days":  len(grp),               # 该周实际交易日数
        })

    if not rows:
        return pd.DataFrame(
            columns=["date","open","high","low","close","volume","amount","_days"]
        )
    result = pd.DataFrame(rows).reset_index(drop=True)
    result["date"] = pd.to_datetime(result["date"])
    return result


def get_current_week_info() -> Tuple[bool, float]:
    """
    返回本周状态：
      (is_complete, vol_scale_factor)
      - is_complete:      本周是否已完整收盘
      - vol_scale_factor: 当周成交量放大系数（用于未完成周的量均线修正）

    放大逻辑：
      如果本周应有5天，已完成2天，当周量是完整周的 2/5
      放大系数 = 5/2 = 2.5，即 annualized_vol = raw_vol * scale
      节假日周同理，比如本周只有2个交易日（春节周），
      已完成1天，scale = 2/1 = 2.0
    """
    today = datetime.date.today()
    weekday = today.weekday()  # 0=周一, 6=周日

    # 周末，上周已完整
    if weekday >= 5:
        return True, 1.0

    # 计算本周周一
    week_monday = today - datetime.timedelta(days=weekday)

    # 尝试从 baostock 获取精确的本周交易日数
    trade_dates = get_trade_dates_cached(today.year)
    if trade_dates is not None:
        total, completed = get_week_trade_days(trade_dates, week_monday)

        if total == 0:
            # 本周全是节假日，没有交易日
            return True, 1.0

        if completed >= total:
            # 本周交易日已全部完成
            return True, 1.0

        if completed == 0:
            # 今天是本周第一个交易日且尚未收盘
            scale = total / max(0.5, 0.5)  # 保守用0.5天估算
            return False, float(total) / 0.5

        # 正常情况：已完成 completed 天，总共 total 天
        scale = float(total) / float(completed)
        logger.debug(
            f"[calendar] 本周进度: {completed}/{total}天, 放大系数={scale:.2f}"
        )
        return False, scale

    # baostock 失败时降级：用自然日估算（周一=1/5, 周二=2/5...）
    logger.warning("[calendar] 无法获取交易日历，使用自然日估算本周进度")
    if weekday == 4:  # 周五
        return True, 1.0
    completed_approx = weekday + 1   # 周一=1, 周二=2...
    scale = 5.0 / completed_approx
    return False, scale
