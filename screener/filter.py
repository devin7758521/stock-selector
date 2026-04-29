# “””
filter.py

两步筛选：
Step 1 - 静态过滤（代码规则 + 实时快照预筛）
Step 2 - 指标计算（日K → 周K聚合 → 均线/量能指标）

周K模式说明（config.yaml 中 weekly_mode 控制）：
“realtime”  - 含当前未完成周K，当周成交量按交易日进度放大修正
偏离度区间相应放宽（乘以放大系数的平方根，平衡灵敏度）
“completed” - 只用已完整收盘的周K，严格模式
“””

import logging
import threading
import datetime
from datetime import timedelta
from typing import Optional

import pandas as pd

from screener.calendar import resample_weekly, get_current_week_info

logger = logging.getLogger(“stock_selector.filter”)

# ── 漏斗统计（线程安全）─────────────────────────────────────

_lock = threading.Lock()
_stats = {
“total”: 0, “pass_price”: 0, “pass_amount”: 0,
“pass_weeks”: 0, “pass_ma25”: 0, “pass_vol_up”: 0, “pass_dev”: 0,
“pass_macd”: 0,
}

def print_stats():
with _lock:
logger.info(”=” * 55)
logger.info(”【筛选漏斗统计】”)
logger.info(f”  进入计算        : {_stats[‘total’]:>5} 只”)
logger.info(f”  通过价格区间    : {_stats[‘pass_price’]:>5} 只”)
logger.info(f”  通过日成交额    : {_stats[‘pass_amount’]:>5} 只”)
logger.info(f”  周K数据足够    : {_stats[‘pass_weeks’]:>5} 只”)
logger.info(f”  站上25周均线    : {_stats[‘pass_ma25’]:>5} 只”)
logger.info(f”  5周量均线向上   : {_stats[‘pass_vol_up’]:>5} 只”)
logger.info(f”  偏离度通过      : {_stats[‘pass_dev’]:>5} 只”)
logger.info(f”  周K MACD通过    : {_stats[‘pass_macd’]:>5} 只  ← 最终入选”)
logger.info(”=” * 55)

# ─────────────────────────────────────────────────────────────

# Step 1: 静态过滤

# ─────────────────────────────────────────────────────────────

def static_filter(df: pd.DataFrame, cfg: dict, spot_df: pd.DataFrame = None) -> pd.DataFrame:
scfg       = cfg.get(“screener”, {})
min_listed = scfg.get(“min_listed_days”, 730)
price_min  = scfg.get(“price_min”, 3)
price_max  = scfg.get(“price_max”, 70)
# 快照预筛用宽松门槛（下午1点只有半天量）
spot_amount_min = scfg.get(“spot_prefilter_amount”, 200000000)
original = len(df)

```
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
    # ── 覆盖率保护 ────────────────────────────────────────────
    # spot_df 覆盖不足全量 50% 时（如兜底数据源只取了前200只），
    # isin 过滤会把没有 spot 数据的股票全部误杀，应跳过预筛。
    coverage = len(spot_df) / max(len(df), 1)
    if coverage < 0.5:
        logger.warning(
            f"实时快照覆盖率不足（spot={len(spot_df)} 只 / 股票池={len(df)} 只"
            f" = {coverage:.1%}），跳过预筛，避免大量误杀。"
            f"请检查数据源是否被封 IP。"
        )
    else:
        # ── 正确的过滤语义 ────────────────────────────────────
        # 有 spot 数据 且 不满足条件 → 过滤掉
        # 有 spot 数据 且 满足条件   → 保留
        # 没有 spot 数据            → 放行（不能因为没数据就误杀）
        has_spot    = df["code"].isin(spot_df["code"])
        valid_codes = spot_df[
            (spot_df["price"]  >= price_min) &
            (spot_df["price"]  <= price_max) &
            (spot_df["amount"] >= spot_amount_min)
        ]["code"]
        before = len(df)
        df = df[~has_spot | df["code"].isin(valid_codes)]
        logger.info(
            f"快照预筛（价格{price_min}~{price_max}元"
            f" + 实时成交额>={spot_amount_min/1e8:.1f}亿）: "
            f"{before} → {len(df)} 只"
        )
else:
    logger.warning("无实时快照，跳过预筛")

logger.info(f"静态过滤完成: {original} → {len(df)} 只")
return df.reset_index(drop=True)
```

# ─────────────────────────────────────────────────────────────

# Step 2: 指标计算

# ─────────────────────────────────────────────────────────────

def calc_indicators(df_daily: pd.DataFrame, cfg: dict) -> Optional[dict]:
“””
日K → 周K → 计算所有指标
支持 realtime / completed 两种模式
“””
scfg       = cfg.get(“screener”, {})
price_min  = scfg.get(“price_min”, 3)
price_max  = scfg.get(“price_max”, 70)
weekly_ma  = scfg.get(“weekly_ma”, 25)
vol_short  = scfg.get(“vol_ma_short”, 5)
vol_long   = scfg.get(“vol_ma_long”, 60)
dev_min    = scfg.get(“vol_deviation_min”, -0.03)
dev_max    = scfg.get(“vol_deviation_max”, 0.07)
min_amount = scfg.get(“min_daily_amount”, 500000000)
mode       = scfg.get(“weekly_mode”, “realtime”)

```
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
        # 成交量用 sqrt(scale)*0.8 放大（而非线性放大），减少噪声放大
        # 数学推导：线性放大scale倍时噪声也被放大scale倍，但偏离度容忍只放宽sqrt(scale)倍
        # 用sqrt(scale)*0.8放大volume：噪声放大sqrt(scale)*0.8倍，容忍放宽scale^(3/4)*0.8倍可覆盖
        import math
        vol_scale_adj = math.sqrt(vol_scale) * 0.8
        df_w = df_w.copy()
        df_w.loc[df_w.index[-1], "volume"] = int(
            df_w["volume"].iloc[-1] * vol_scale_adj
        )
        df_w.loc[df_w.index[-1], "amount"] = int(
            df_w["amount"].iloc[-1] * vol_scale_adj
        )
        logger.debug(
            f"[realtime] 当周量放大 x{vol_scale_adj:.2f}（sqrt*0.8修正，原始scale={vol_scale:.2f}）"
        )
        # 偏离度容忍放宽: scale^(3/4)*0.8，覆盖约1.2个std
        # 周一: 5^0.75*0.8=2.67x, 周三: 1.67^0.75*0.8=1.20x, 周五: 1.00x
        tolerance = vol_scale ** 0.75 * 0.8
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

# ── 条件：周K MACD DIF > DEA 且偏离值不超过10% ───────────
ema12 = close_w.ewm(span=12, adjust=False).mean()
ema26 = close_w.ewm(span=26, adjust=False).mean()
dif   = ema12 - ema26
dea   = dif.ewm(span=9, adjust=False).mean()
dif_val, dea_val = float(dif.iloc[idx]), float(dea.iloc[idx])
if pd.isna(dif_val) or pd.isna(dea_val) or dif_val <= dea_val:
    return None
dea_abs = abs(dea_val)
if dea_abs > 1e-9 and (dif_val - dea_val) / dea_abs > 0.15:
    return None
with _lock:
    _stats["pass_macd"] += 1

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
```