# -*- coding: utf-8 -*-
"""
ETF周K筛选模块

使用与个股/板块相同的周K参数筛选ETF：
- 25周均线
- 5周量均线向上
- 量能偏离度
- 成交额门槛

去重逻辑：追踪同一指数的多只ETF，只取成交额最大的一只参与筛选。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from screener.calendar import resample_weekly, get_current_week_info

logger = logging.getLogger("stock_selector.etf")


def fetch_etf_list_with_index() -> Optional[pd.DataFrame]:
    """获取ETF列表（含跟踪指数信息）"""
    try:
        import akshare as ak
        df = ak.fund_info_index_em(symbol="全部", indicator="被动指数型")
        if df is not None and not df.empty:
            df = df.rename(columns={
                "基金代码": "code",
                "基金名称": "name",
                "跟踪标的": "index_name",
            })
            logger.info(f"[etf] 被动指数型ETF: {len(df)} 个")
            return df[["code", "name", "index_name"]]
    except Exception as e:
        logger.debug(f"[etf] fund_info_index_em失败: {e}")
    return None


def fetch_etf_kline(symbol: str, days: int = 730) -> Optional[pd.DataFrame]:
    """获取ETF日K线数据"""
    try:
        import akshare as ak
        df = ak.fund_etf_hist_em(symbol=symbol, period="日k",
                                 start_date=(datetime.today() - timedelta(days=days)).strftime("%Y%m%d"),
                                 end_date="20991231", adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low",
                "成交量": "volume", "成交额": "amount",
            })
            for c in ["open", "high", "low", "close", "volume", "amount"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df["date"] = pd.to_datetime(df["date"])
            df = df.dropna().sort_values("date").reset_index(drop=True)
            return df if len(df) >= 200 else None
    except Exception as e:
        logger.debug(f"[etf/kline] {symbol}: {e}")
    return None


def deduplicate_by_index(etf_df: pd.DataFrame, min_amount: float = 50000000) -> pd.DataFrame:
    """
    按跟踪指数去重：每只跟踪指数只保留成交额最大的ETF

    Args:
        etf_df: 包含 code, name, index_name 的 DataFrame
        min_amount: 最小日成交额门槛（元），低于此值不参与去重排名

    Returns:
        去重后的 DataFrame
    """
    etf_df = etf_df.copy()
    etf_df["amount_rank"] = 0.0

    for idx, row in etf_df.iterrows():
        try:
            df = fetch_etf_kline(row["code"])
            if df is not None and not df.empty:
                amt = float(df["amount"].iloc[-1])
            else:
                amt = 0.0
            etf_df.at[idx, "amount_rank"] = amt
        except Exception:
            etf_df.at[idx, "amount_rank"] = 0.0

    etf_df = etf_df[etf_df["amount_rank"] >= min_amount]
    if etf_df.empty:
        return etf_df

    etf_df = etf_df.sort_values("amount_rank", ascending=False)
    etf_dedup = etf_df.groupby("index_name", sort=False).first().reset_index()
    logger.info(f"[etf] 去重后: {len(etf_dedup)} 只ETF（每指数一只）")
    return etf_dedup


def filter_etf_weekly(cfg: dict) -> List[Dict]:
    """
    用与板块相同的周K参数筛选ETF

    Returns:
        通过筛选的ETF列表 [{"code", "name", "index_name", "price", "vol_deviation_pct",
                            "daily_amount_yi", "ma25_weekly", "etf_trend"}]
    """
    scfg = cfg.get("screener", {})
    weekly_ma = scfg.get("weekly_ma", 25)
    vol_short = scfg.get("vol_ma_short", 5)
    vol_long = scfg.get("vol_ma_long", 60)
    dev_min = scfg.get("vol_deviation_min", -0.03)
    dev_max = scfg.get("vol_deviation_max", 0.07)
    min_amount = scfg.get("min_daily_amount", 300000000)
    mode = scfg.get("weekly_mode", "realtime")

    etf_raw = fetch_etf_list_with_index()
    if etf_raw is None or etf_raw.empty:
        logger.warning("[etf] 无法获取ETF列表，跳过ETF筛选")
        return []

    etf_df = deduplicate_by_index(etf_raw, min_amount=min_amount)
    if etf_df.empty:
        logger.warning("[etf] 去重后无ETF，跳过ETF筛选")
        return []

    passed = []
    total = len(etf_df)

    for idx, row in etf_df.iterrows():
        code = str(row["code"])
        name = str(row["name"])
        index_name = str(row.get("index_name", ""))

        df_daily = fetch_etf_kline(code)
        if df_daily is None or len(df_daily) < 200:
            continue

        latest_price = df_daily["close"].iloc[-1]
        latest_amount = df_daily["amount"].iloc[-1]

        if latest_amount < min_amount:
            continue

        df_w = resample_weekly(df_daily)
        min_weeks = max(weekly_ma, vol_long) + 2
        if len(df_w) < min_weeks:
            continue

        is_week_complete, vol_scale = get_current_week_info()

        if mode == "completed" and not is_week_complete:
            df_w = df_w.iloc[:-1].reset_index(drop=True)
            if len(df_w) < min_weeks:
                continue

        if mode == "realtime" and not is_week_complete and vol_scale > 1.0:
            df_w = df_w.copy()
            import math
            vol_scale_adj = math.sqrt(vol_scale) * 0.8
            df_w.loc[df_w.index[-1], "volume"] = int(df_w["volume"].iloc[-1] * vol_scale_adj)
            df_w.loc[df_w.index[-1], "amount"] = int(df_w["amount"].iloc[-1] * vol_scale_adj)
            tolerance = vol_scale ** 0.75 * 0.8
            actual_dev_min = dev_min * tolerance
            actual_dev_max = dev_max * tolerance
        else:
            actual_dev_min = dev_min
            actual_dev_max = dev_max

        close_w = df_w["close"]
        volume_w = df_w["volume"]

        ma25_w = close_w.rolling(weekly_ma).mean()
        if pd.isna(ma25_w.iloc[-1]) or close_w.iloc[-1] <= ma25_w.iloc[-1]:
            continue

        vol_ma5_w = volume_w.rolling(vol_short).mean()
        if pd.isna(vol_ma5_w.iloc[-1]) or pd.isna(vol_ma5_w.iloc[-2]):
            continue
        if vol_ma5_w.iloc[-1] <= vol_ma5_w.iloc[-2]:
            continue

        vol_ma60_w = volume_w.rolling(vol_long).mean()
        if pd.isna(vol_ma60_w.iloc[-1]) or vol_ma60_w.iloc[-1] == 0:
            continue
        deviation = (vol_ma5_w.iloc[-1] - vol_ma60_w.iloc[-1]) / vol_ma60_w.iloc[-1]
        if not (actual_dev_min <= deviation <= actual_dev_max):
            continue

        if deviation > 0.03:
            etf_trend = "放量上行"
        elif deviation > 0:
            etf_trend = "温和上行"
        elif deviation > -0.02:
            etf_trend = "缩量整理"
        else:
            etf_trend = "缩量下行"

        passed.append({
            "code": code,
            "name": name,
            "index_name": index_name,
            "price": round(latest_price, 4),
            "vol_deviation_pct": round(deviation * 100, 2),
            "daily_amount_yi": round(latest_amount / 1e8, 2),
            "ma25_weekly": round(ma25_w.iloc[-1], 4),
            "etf_trend": etf_trend,
        })

    logger.info(f"[etf] ETF筛选: {total} → {len(passed)} 个通过")
    return passed
