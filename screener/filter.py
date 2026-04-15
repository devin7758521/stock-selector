"""
filter.py
=========
两步筛选：
  Step 1 - 静态过滤（代码规则 + 实时快照预筛）
  Step 2 - 指标计算（日K → 周K聚合 → 均线/量能指标）

周K模式说明（config.yaml 中 weekly_mode 控制）：
  "realtime"  - 含当前未完成周K，当周成交量按交易日进度放大修正
                偏离度区间相应放宽（乘以放大系数的平方根，平衡灵敏度）
  "completed" - 只用已完整收盘的周K，严格模式
"""

import logging
import threading
import datetime
from datetime import timedelta
from typing import Optional

import pandas as pd

from screener.calendar import resample_weekly, get_current_week_info

logger = logging.getLogger("stock_selector.filter")

# ── 漏斗统计（线程安全）─────────────────────────────────────
_lock = threading.Lock()
_stats = {
    "total": 0, "pass_price": 0, "pass_amount": 0,
    "pass_weeks": 0, "pass_ma25": 0, "pass_vol_up": 0, "pass_dev": 0,
}


def print_stats():
    with _lock:
        logger.info("=" * 55)
        logger.info("【筛选漏斗统计】")
        logger.info(f"  进入计算        : {_stats['total']:>5} 只")
        logger.info(f"  通过价格区间    : {_stats['pass_price']:>5} 只")
        logger.info(f"  通过日成交额    : {_stats['pass_amount']:>5} 只")
        logger.info(f"  周K数据足够    : {_stats['pass_weeks']:>5} 只")
        logger.info(f"  站上25周均线    : {_stats['pass_ma25']:>5} 只")
        logger.info(f"  5周量均线向上   : {_stats['pass_vol_up']:>5} 只")
        logger.info(f"  偏离度通过      : {_stats['pass_dev']:>5} 只  ← 最终入选")
        logger.info("=" * 55)


# ─────────────────────────────────────────────────────────────
# Step 1: 静态过滤
# ─────────────────────────────────────────────────────────────
def static_filter(df: pd.DataFrame, cfg: dict, spot_df: pd.DataFrame = None) -> pd.DataFrame:
    scfg       = cfg.get("screener", {})
    min_listed = scfg.get("min_listed_days", 730)
    price_min  = scfg.get("price_min", 3)
    price_max  = scfg.get("price_max", 70)
    # 快照预筛用宽松门槛（下午1点只有半天量）
    spot_amount_min = scfg.get("spot_prefilter_amount", 200000000)
    original = len(df)

    df = df[~df["code"].str.startswith("688")]
    df = df[~df["code"].str.startswith(("300", "301"))]
    df = df[~df["code"].str.startswith(("8", "4"))]
    df = df[~df["name"].str.contains(r"\*?ST", regex=True, na=False)]

    cutoff = (datetime.datetime.today() - timedelta(days=min_listed)).strftime("%Y%m%d")
    df["list_date"] = df["list_date"].astype(str).str.replace("-", "")
    df = df[df["list_date"].str.len() == 8]
    df = df[df["list_date"] <= cutoff]
    logger.info(f"代码/名称过滤: {original} → {len(df)} 只")

    if spot_df is not None and not spot_df.empty:
        valid = spot_df[
            (spot_df["price"]  >= price_min) &
            (spot_df["price"]  <= price_max) &
            (spot_df["amount"] >= spot_amount_min)
        ]["code"]
        before = len(df)
        df = df[df["code"].isin(valid)]
        logger.info(
            f"快照预筛（价格{price_min}~{price_max}元 + 实时成交额>={spot_amount_min/1e8:.1f}亿）: "
            f"{before} → {len(df)} 只"
        )
    else:
        logger.warning("无实时快照，跳过预筛")

    logger.info(f"静态过滤完成: {original} → {len(df)} 只")
    return df.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# Step 2: 指标计算
# ─────────────────────────────────────────────────────────────
def calc_indicators(df_daily: pd.DataFrame, cfg: dict) -> Optional[dict]:
    """
    日K → 周K → 计算所有指标
    支持 realtime / completed 两种模式
    """
    scfg       = cfg.get("screener", {})
    price_min  = scfg.get("price_min", 3)
    price_max  = scfg.get("price_max", 70)
    weekly_ma  = scfg.get("weekly_ma", 25)
    vol_short  = scfg.get("vol_ma_short", 5)
    vol_long   = scfg.get("vol_ma_long", 60)
    dev_min    = scfg.get("vol_deviation_min", -0.03)
    dev_max    = scfg.get("vol_deviation_max", 0.07)
    min_amount = scfg.get("min_daily_amount", 500000000)
    mode       = scfg.get("weekly_mode", "realtime")

    with _lock:
        _stats["total"] += 1

    # ── 日K精确判断 ──────────────────────────────────────────
    latest_price = df_daily["close"].iloc[-1]
    latest_daily_amount = df_daily["amount"].iloc[-1]

    if not (price_min <= latest_price <= price_max):
        return None
    with _lock:
        _stats["pass_price"] += 1

    # 成交额判断
    if latest_daily_amount < min_amount:
        logger.debug(f"成交额不达标: {latest_daily_amount/1e8:.2f}亿 < {min_amount/1e8:.2f}亿")
        return None
    with _lock:
        _stats["pass_amount"] += 1
        logger.debug(f"成交额达标: {latest_daily_amount/1e8:.2f}亿 >= {min_amount/1e8:.2f}亿")

    # ── 日K → 周K ───────────────────────────────────────────
    df_w = resample_weekly(df_daily)
    min_weeks = max(weekly_ma, vol_long) + 2
    if len(df_w) < min_weeks:
        return None
    with _lock:
        _stats["pass_weeks"] += 1

    # ── 模式选择 ─────────────────────────────────────────────
    is_week_complete, vol_scale = get_current_week_info()

    if mode == "completed":
        # 严格模式：只用已完成的周K
        # 未完成则去掉最后一根，用倒数第二根
        if not is_week_complete:
            df_w = df_w.iloc[:-1].reset_index(drop=True)
            if len(df_w) < min_weeks:
                return None
        idx = -1
        # 偏离度不放宽
        actual_dev_min = dev_min
        actual_dev_max = dev_max

    else:
        # realtime 模式：含未完成周，量能按进度放大
        idx = -1
        if not is_week_complete and vol_scale > 1.0:
            # 将当周成交量按进度放大，还原完整周估算值
            df_w = df_w.copy()
            df_w.loc[df_w.index[-1], "volume"] = (
                df_w["volume"].iloc[-1] * vol_scale
            )
            df_w.loc[df_w.index[-1], "amount"] = (
                df_w["amount"].iloc[-1] * vol_scale
            )
            logger.debug(
                f"[realtime] 当周量放大 x{vol_scale:.2f}（交易日进度补偿）"
            )
            # 偏离度适当放宽：放大系数越大（周中越早），容忍范围越宽
            # 用 sqrt(scale) 平衡：周一(scale≈5)放宽2.2倍，周四(scale≈1.25)放宽1.1倍
            import math
            tolerance = math.sqrt(vol_scale)
            actual_dev_min = dev_min * tolerance
            actual_dev_max = dev_max * tolerance
            logger.debug(
                f"[realtime] 偏离度容忍放宽 x{tolerance:.2f}: "
                f"[{actual_dev_min:.2%}, {actual_dev_max:.2%}]"
            )
        else:
            actual_dev_min = dev_min
            actual_dev_max = dev_max

    close_w  = df_w["close"]
    volume_w = df_w["volume"]

    # ── 条件：25周均线 ───────────────────────────────────────
    ma25_w = close_w.rolling(weekly_ma).mean()
    if pd.isna(ma25_w.iloc[idx]) or close_w.iloc[idx] <= ma25_w.iloc[idx]:
        return None
    with _lock:
        _stats["pass_ma25"] += 1

    # ── 条件：5周量均线向上 ──────────────────────────────────
    vol_ma5_w = volume_w.rolling(vol_short).mean()
    prev_idx  = idx - 1
    if (
        pd.isna(vol_ma5_w.iloc[idx]) or
        pd.isna(vol_ma5_w.iloc[prev_idx]) or
        vol_ma5_w.iloc[idx] <= vol_ma5_w.iloc[prev_idx]
    ):
        return None
    with _lock:
        _stats["pass_vol_up"] += 1

    # ── 条件：偏离度 ─────────────────────────────────────────
    vol_ma60_w = volume_w.rolling(vol_long).mean()
    if pd.isna(vol_ma60_w.iloc[idx]) or vol_ma60_w.iloc[idx] == 0:
        return None
    deviation = (vol_ma5_w.iloc[idx] - vol_ma60_w.iloc[idx]) / vol_ma60_w.iloc[idx]
    if not (actual_dev_min <= deviation <= actual_dev_max):
        logger.debug(
            f"偏离度不符: {deviation:.2%} 区间=[{actual_dev_min:.2%}, {actual_dev_max:.2%}]"
        )
        return None
    with _lock:
        _stats["pass_dev"] += 1

    return {
        "price":             round(latest_price, 2),
        "ma25_weekly":       round(ma25_w.iloc[idx], 2),
        "vol_ma5_weekly":    round(float(vol_ma5_w.iloc[idx]), 0),
        "vol_ma60_weekly":   round(float(vol_ma60_w.iloc[idx]), 0),
        "vol_deviation_pct": round(deviation * 100, 2),
        "daily_amount_yi":   round(latest_daily_amount / 1e8, 2),
        "week_complete":     is_week_complete,
        "weekly_mode":       mode,
    }
