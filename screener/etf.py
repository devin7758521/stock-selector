# -*- coding: utf-8 -*-
"""
ETF周K筛选模块

使用与个股/板块相同的周K参数筛选ETF：
- 25周均线
- 5周量均线向上
- 量能偏离度
- 成交额门槛

去重逻辑：用东方财富实时行情获取成交额，从ETF名称提取指数关键字去重，
同一指数只取成交额最大的一只参与筛选。
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

from screener.calendar import resample_weekly, get_current_week_info
from screener.utils import random_headers

logger = logging.getLogger("stock_selector.etf")


def fetch_etf_spot_em(min_amount: float = 0) -> Optional[pd.DataFrame]:
    """
    通过东方财富HTTP接口获取ETF实时行情（含成交额），一次性获取所有ETF

    Args:
        min_amount: 最小日成交额过滤（元），0=不过滤

    Returns:
        DataFrame with columns: code, name, price, gain_pct, amount, index_key
    """
    try:
        all_items = []
        page, page_size = 1, 500
        while True:
            url = "https://push2.eastmoney.com/api/qt/clist/get"
            params = {
                "pn": str(page), "pz": str(page_size), "po": "1", "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2", "invt": "2", "fid": "f6",
                "fs": "b:MK0021",
                "fields": "f12,f14,f2,f3,f6",
            }
            resp = requests.get(url, params=params, headers=random_headers(), timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            diff = data.get("diff", []) or []
            if not diff:
                break
            all_items.extend(diff)
            total = data.get("total", 0)
            if page * page_size >= total:
                break
            page += 1

        if not all_items:
            logger.warning("[etf] 东方财富ETF实时行情为空")
            return None

        rows = []
        for i in all_items:
            code = str(i.get("f12", ""))
            name = str(i.get("f14", ""))
            amount = i.get("f6", 0)
            if amount == "-" or amount is None:
                amount = 0.0
            price = i.get("f2", 0)
            if price == "-" or price is None:
                price = 0.0
            gain = i.get("f3", 0)
            if gain == "-" or gain is None:
                gain = 0.0
            rows.append({
                "code": code,
                "name": name,
                "price": float(price),
                "gain_pct": float(gain),
                "amount": float(amount),
            })

        df = pd.DataFrame(rows)
        if min_amount > 0:
            df = df[df["amount"] >= min_amount]
        df = df.reset_index(drop=True)
        logger.info(f"[etf] 东方财富ETF实时行情: {len(df)} 只（成交额>={min_amount/1e8:.1f}亿）")
        return df
    except Exception as e:
        logger.debug(f"[etf] 东方财富ETF实时行情失败: {e}")
    return None


def fetch_etf_list_akshare() -> Optional[pd.DataFrame]:
    """通过akshare获取ETF列表（备源）"""
    try:
        import akshare as ak
        df = ak.fund_info_index_em(symbol="全部", indicator="被动指数型")
        if df is not None and not df.empty:
            df = df.rename(columns={
                "基金代码": "code",
                "基金名称": "name",
                "跟踪标的": "index_name",
            })
            logger.info(f"[etf] akshare被动指数型ETF: {len(df)} 个")
            return df[["code", "name", "index_name"]]
    except Exception as e:
        logger.debug(f"[etf] fund_info_index_em失败: {e}")
    return None


def _extract_index_key(name: str) -> str:
    """
    从ETF名称中提取指数关键字用于去重

    例: "通信ETF国泰" → "通信"
        "沪深300ETF易方达" → "沪深300"
        "中证500ETF" → "中证500"
        "创业板人工智能ETF华夏" → "创业板人工智能"
    """
    # 去掉ETF后缀及基金公司名
    s = re.sub(r'ETF[A-Za-z\u4e00-\u9fff]*$', '', name, flags=re.IGNORECASE)
    s = re.sub(r'指数[AC]$', '', s)
    s = s.strip()
    return s if s else name


def deduplicate_by_index(etf_df: pd.DataFrame) -> pd.DataFrame:
    """
    按指数关键字去重：同一指数只保留成交额最大的ETF

    Args:
        etf_df: 必须含 code, name, amount 列

    Returns:
        去重后的 DataFrame
    """
    etf_df = etf_df.copy()
    etf_df["index_key"] = etf_df["name"].apply(_extract_index_key)
    etf_df = etf_df.sort_values("amount", ascending=False)
    etf_dedup = etf_df.groupby("index_key", sort=False).first().reset_index()
    logger.info(f"[etf] 去重后: {len(etf_dedup)} 只ETF（每指数一只，原始{len(etf_df)}只）")
    return etf_dedup


def _etf_secid(code: str) -> str:
    """ETF代码转东方财富secid：5开头→1.x，1/3开头→0.x"""
    return f"1.{code}" if code.startswith("5") else f"0.{code}"


def _fetch_etf_eastmoney(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    """东方财富HTTP获取ETF日K线（主力，多线程安全）"""
    try:
        start_date = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": _etf_secid(code),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "klt": "101", "fqt": "1",
            "beg": start_date, "end": "20991231", "lmt": "1000",
        }
        resp = requests.get(url, params=params, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        klines = (resp.json().get("data") or {}).get("klines", [])
        if not klines:
            return None
        rows = []
        for k in klines:
            p = k.split(",")
            rows.append({
                "date": p[0], "open": p[1], "close": p[2],
                "high": p[3], "low": p[4], "volume": p[5], "amount": p[6],
            })
        df = pd.DataFrame(rows)
        for c in ["open", "high", "low", "close", "volume", "amount"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna().sort_values("date").reset_index(drop=True)
        return df if len(df) >= 200 else None
    except Exception as e:
        logger.debug(f"[etf/eastmoney] {code}: {e}")
    return None


def _fetch_etf_akshare(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    """akshare获取ETF日K线（备源）"""
    try:
        import akshare as ak
        df = ak.fund_etf_hist_em(symbol=code, period="日k",
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
        logger.debug(f"[etf/akshare] {code}: {e}")
    return None


def fetch_etf_kline(symbol: str, days: int = 730) -> Optional[pd.DataFrame]:
    """获取ETF日K线数据（多源轮换：东方财富→akshare）"""
    df = _fetch_etf_eastmoney(symbol, days)
    if df is not None:
        return df
    return _fetch_etf_akshare(symbol, days)


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

    # 主源：东方财富实时行情（一次性获取成交额，避免逐个请求K线）
    etf_spot = fetch_etf_spot_em(min_amount=min_amount)

    if etf_spot is not None and not etf_spot.empty:
        etf_df = deduplicate_by_index(etf_spot)
    else:
        # 备源：akshare（无成交额，需要逐个请求K线）
        etf_raw = fetch_etf_list_akshare()
        if etf_raw is None or etf_raw.empty:
            logger.warning("[etf] 无法获取ETF列表，跳过ETF筛选")
            return []
        # 对akshare来源，先按成交额预筛（逐个K线），但降低门槛防止全过滤
        etf_raw["amount"] = 0.0
        for idx, row in etf_raw.iterrows():
            try:
                df_k = fetch_etf_kline(row["code"])
                if df_k is not None and not df_k.empty:
                    etf_raw.at[idx, "amount"] = float(df_k["amount"].iloc[-1])
            except Exception:
                pass
        etf_raw = etf_raw[etf_raw["amount"] >= min_amount]
        if etf_raw.empty:
            logger.warning("[etf] akshare来源ETF成交额均不达标，跳过ETF筛选")
            return []
        etf_df = deduplicate_by_index(etf_raw)

    if etf_df.empty:
        logger.warning("[etf] 去重后无ETF，跳过ETF筛选")
        return []

    passed = []
    total = len(etf_df)

    for idx, row in etf_df.iterrows():
        code = str(row["code"])
        name = str(row["name"])

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
            "index_name": str(row.get("index_key", "")),
            "price": round(latest_price, 4),
            "vol_deviation_pct": round(deviation * 100, 2),
            "daily_amount_yi": round(latest_amount / 1e8, 2),
            "ma25_weekly": round(ma25_w.iloc[-1], 4),
            "etf_trend": etf_trend,
        })

    logger.info(f"[etf] ETF筛选: {total} → {len(passed)} 个通过")
    return passed
