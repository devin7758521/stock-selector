# -*- coding: utf-8 -*-
"""
大盘环境分析模块

判断当前市场环境：多头/震荡/空头，给出仓位建议。

数据源（三通道降级）：
  主源: akshare → 备源: adata（多源融合,代理支持）→ 兜底: 东方财富HTTP
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

import pandas as pd
import requests

from screener.utils import random_headers

logger = logging.getLogger("stock_selector.market_env")

INDEX_MAP = {
    "sh000001": {"code": "000001", "name": "上证指数", "market": 1},
    "sz399006": {"code": "399006", "name": "创业板指", "market": 0},
}


# ═══════════════════════════════════════════════════════
# 数据源层：akshare → adata → eastmoney 三级降级
# ═══════════════════════════════════════════════════════

def _fetch_index_akshare(code: str, days: int = 120) -> Optional[pd.DataFrame]:
    """主源: akshare 指数日K"""
    try:
        import akshare as ak
        symbol = f"sh{code}" if code == "000001" else f"sz{code}"
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is not None and not df.empty:
            df = df.rename(columns={
                "date": "date", "open": "open", "close": "close",
                "high": "high", "low": "low", "volume": "volume",
            })
            df["date"] = pd.to_datetime(df["date"])
            start = datetime.today() - timedelta(days=days + 30)
            df = df[df["date"] >= start]
            for c in ["open", "high", "low", "close", "volume"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna().sort_values("date").reset_index(drop=True)
            if len(df) >= 30:
                return df
    except Exception as e:
        logger.debug(f"akshare指数 {code} 失败: {e}")
    return None


def _fetch_index_adata(code: str, days: int = 120) -> Optional[pd.DataFrame]:
    """备源: adata（融合同花顺+东财+新浪+腾讯，自带代理切换）"""
    try:
        import adata
        start = (datetime.today() - timedelta(days=days + 30)).strftime("%Y-%m-%d")
        df = adata.stock.market.get_market_index(
            index_code=code, k_type=1, start_date=start
        )
        if df is not None and not df.empty:
            col_map = {}
            for col in df.columns:
                cl = col.lower()
                if "date" in cl or "日期" in col:
                    col_map[col] = "date"
                elif "open" in cl or "开" in col:
                    col_map[col] = "open"
                elif "high" in cl or "高" in col:
                    col_map[col] = "high"
                elif "low" in cl or "低" in col:
                    col_map[col] = "low"
                elif "close" in cl or "收" in col:
                    col_map[col] = "close"
                elif "volume" in cl or "量" in col:
                    col_map[col] = "volume"
            df = df.rename(columns=col_map)
            keep = ["date", "open", "high", "low", "close", "volume"]
            df = df[[c for c in keep if c in df.columns]]
            df["date"] = pd.to_datetime(df["date"])
            for c in ["open", "high", "low", "close", "volume"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            df = df.dropna().sort_values("date").reset_index(drop=True)
            if len(df) >= 30:
                return df
    except Exception as e:
        logger.debug(f"adata指数 {code} 失败: {e}")
    return None


def _fetch_index_eastmoney(code: str, market: int, days: int = 120) -> Optional[pd.DataFrame]:
    """兜底: 东方财富HTTP日K"""
    try:
        secid = f"{market}.{code}"
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid,
            "ut": "fa5fd1943c7b386f172d6893dbfd10b4",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "klt": "101", "fqt": "1", "end": "20500101", "lmt": str(days),
        }
        resp = requests.get(url, params=params, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("data") and data["data"].get("klines"):
            rows = []
            for line in data["data"]["klines"]:
                parts = line.split(",")
                rows.append({
                    "date": parts[0], "open": float(parts[1]),
                    "close": float(parts[2]), "high": float(parts[3]),
                    "low": float(parts[4]), "volume": float(parts[5]),
                })
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
    except Exception as e:
        logger.debug(f"东方财富指数 {code} 失败: {e}")
    return None


def fetch_index_data(code: str, name: str, market: int, days: int = 120) -> Optional[pd.DataFrame]:
    """三通道降级: akshare → adata → eastmoney"""
    # 主源: akshare
    df = _fetch_index_akshare(code, days)
    if df is not None:
        return df

    # 备源: adata（多源融合，可在GitHub Actions上用代理）
    logger.warning(f"{name} akshare失败 → 尝试 adata")
    df = _fetch_index_adata(code, days)
    if df is not None:
        return df

    # 兜底: 东方财富HTTP
    logger.warning(f"{name} adata失败 → 降级东方财富")
    return _fetch_index_eastmoney(code, market, days)


# ═══════════════════════════════════════════════════════
# 指标计算
# ═══════════════════════════════════════════════════════

def _calc_ma_signal(close: pd.Series, days: int) -> Tuple[bool, float]:
    ma = close.rolling(days).mean()
    if pd.isna(ma.iloc[-1]):
        return False, 0
    return float(close.iloc[-1]) > float(ma.iloc[-1]), round(float(ma.iloc[-1]), 2)


def _calc_volume_trend(volume: pd.Series, periods: int = 5) -> str:
    if len(volume) < periods + 5:
        return "数据不足"
    recent = volume.iloc[-periods:].mean()
    baseline = volume.iloc[-(periods + 5):-periods].mean()
    if baseline <= 0:
        return "数据不足"
    ratio = recent / baseline
    if ratio > 1.15:
        return "放量"
    elif ratio < 0.85:
        return "缩量"
    return "持平"


# ═══════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════

def analyze_market_env(days: int = 120) -> Dict:
    """分析大盘环境，返回评分+仓位+情绪"""
    details = {}
    above_ma25_count = 0
    above_ma60_count = 0
    vol_expand_count = 0
    valid_count = 0

    for key, info in INDEX_MAP.items():
        df = fetch_index_data(info["code"], info["name"], info["market"], days)
        if df is None or len(df) < 30:
            logger.warning(f"{info['name']} 数据不足，跳过")
            details[info["name"]] = {
                "close": 0, "above_ma25": False, "above_ma60": False,
                "ma25": 0, "ma60": 0, "vol_trend": "数据不足",
                "daily_gain_pct": 0, "error": "数据不足",
            }
            continue

        valid_count += 1
        close = df["close"]
        volume = df["volume"]

        above_25, ma25 = _calc_ma_signal(close, 25)
        above_60, ma60 = _calc_ma_signal(close, 60)
        vol_trend = _calc_volume_trend(volume)

        if above_25:
            above_ma25_count += 1
        if above_60:
            above_ma60_count += 1
        if vol_trend == "放量":
            vol_expand_count += 1

        daily_gain = round(
            (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2
        ) if len(close) >= 2 else 0

        details[info["name"]] = {
            "close": round(float(close.iloc[-1]), 2),
            "above_ma25": above_25, "above_ma60": above_60,
            "ma25": ma25, "ma60": ma60,
            "vol_trend": vol_trend, "daily_gain_pct": daily_gain,
        }

    if valid_count == 0:
        return {
            "score": 0, "position_pct": 0, "sentiment": "回避",
            "summary": "指数数据获取失败（akshare+adata+东财均失败），建议观望",
            "indices": details, "market_breadth": "未知",
            "warning": "⚠️ 所有数据源均不可用，请检查网络",
        }

    # 评分
    score = 50
    if above_ma25_count == valid_count and above_ma60_count == valid_count:
        score += 30
        breadth = "均线多头排列"
    elif above_ma25_count >= valid_count // 2 + 1:
        score += 10
        breadth = "均线偏多"
    elif above_ma25_count == 0:
        score -= 20
        breadth = "均线空头排列"
    else:
        breadth = "均线分化"

    if vol_expand_count >= valid_count:
        score += 20
        breadth += " + 量能放大"
    elif vol_expand_count == 0:
        score -= 15
        breadth += " + 量能萎缩"
    else:
        breadth += " + 量能分化"

    sh_daily = details.get("上证指数", {}).get("daily_gain_pct", 0)
    if sh_daily > 1:
        score += 5
    elif sh_daily < -2:
        score -= 10

    score = max(0, min(100, score))

    if score >= 70:
        sentiment, position_pct, warning = "乐观", 50, ""
    elif score >= 45:
        sentiment, position_pct, warning = "中性", 20, ""
    elif score >= 25:
        sentiment, position_pct, warning = "谨慎", 10, "⚠️ 市场偏弱，建议轻仓或观望"
    else:
        sentiment, position_pct, warning = "回避", 0, "⚠️ 市场环境差，建议空仓等待"

    return {
        "score": score, "position_pct": position_pct,
        "sentiment": sentiment, "summary": f"市场评分{score}/100，情绪{sentiment}，建议仓位{position_pct}%",
        "indices": details, "market_breadth": breadth, "warning": warning,
    }
