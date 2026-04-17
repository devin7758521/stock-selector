# -*- coding: utf-8 -*-
"""
板块周K筛选模块

使用与个股相同的周K参数筛选板块：
- 25周均线
- 5周量均线向上
- 量能偏离度
- 成交额门槛

不涉及LLM分析/新闻，纯技术面筛选。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

from screener.calendar import resample_weekly, get_current_week_info
from screener.utils import random_headers

logger = logging.getLogger("stock_selector.sector")


def fetch_sector_list() -> Optional[pd.DataFrame]:
    """获取东方财富行业板块列表"""
    try:
        import akshare as ak
        df = ak.stock_board_industry_name_em()
        if df is not None and not df.empty:
            df = df.rename(columns={
                "板块名称": "name",
                "板块代码": "code",
            })
            logger.info(f"[sector] 东方财富行业板块: {len(df)} 个")
            return df[["code", "name"]]
    except Exception as e:
        logger.debug(f"[sector] akshare板块列表失败: {e}")

    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "200", "po": "1", "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:90+t:2+f:!50",
            "fields": "f12,f14",
        }
        resp = requests.get(url, params=params, headers=random_headers(), timeout=15)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        if items:
            df = pd.DataFrame([{
                "code": i["f12"], "name": i["f14"]
            } for i in items])
            logger.info(f"[sector] 东方财富HTTP板块: {len(df)} 个")
            return df
    except Exception as e:
        logger.debug(f"[sector] 东方财富HTTP板块失败: {e}")

    return None


def fetch_sector_kline(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    """获取板块日K线数据"""
    try:
        import akshare as ak
        df = ak.stock_board_industry_hist_em(
            symbol=code, period="日k",
            start_date=(datetime.today() - timedelta(days=days)).strftime("%Y%m%d"),
            end_date="20991231", adjust=""
        )
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
        logger.debug(f"[sector/kline] {code}: {e}")
    return None


def filter_sector_weekly(cfg: dict) -> List[Dict]:
    """
    用与个股相同的周K参数筛选板块

    Returns:
        通过筛选的板块列表 [{"code", "name", "price", "vol_deviation_pct",
                              "daily_amount_yi", "ma25_weekly", "sector_trend"}]
    """
    scfg = cfg.get("screener", {})
    weekly_ma = scfg.get("weekly_ma", 25)
    vol_short = scfg.get("vol_ma_short", 5)
    vol_long = scfg.get("vol_ma_long", 60)
    dev_min = scfg.get("vol_deviation_min", -0.03)
    dev_max = scfg.get("vol_deviation_max", 0.07)
    min_amount = scfg.get("min_daily_amount", 300000000)
    mode = scfg.get("weekly_mode", "realtime")

    sector_df = fetch_sector_list()
    if sector_df is None or sector_df.empty:
        logger.warning("[sector] 无法获取板块列表，跳过板块筛选")
        return []

    passed = []
    total = len(sector_df)

    for idx, row in sector_df.iterrows():
        code = str(row["code"])
        name = str(row["name"])

        df_daily = fetch_sector_kline(name)
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
            sector_trend = "放量上行"
        elif deviation > 0:
            sector_trend = "温和上行"
        elif deviation > -0.02:
            sector_trend = "缩量整理"
        else:
            sector_trend = "缩量下行"

        passed.append({
            "code": code,
            "name": name,
            "price": round(latest_price, 2),
            "vol_deviation_pct": round(deviation * 100, 2),
            "daily_amount_yi": round(latest_amount / 1e8, 2),
            "ma25_weekly": round(ma25_w.iloc[-1], 2),
            "sector_trend": sector_trend,
        })

    logger.info(f"[sector] 板块筛选: {total} → {len(passed)} 个通过")
    return passed
