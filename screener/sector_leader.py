# -*- coding: utf-8 -*-
"""
主线板块识别 + 龙头选股模块

Top-down选股流程：
1. 涨停板数据：akshare → pywencai(问财) → 东方财富 三级降级
2. 板块详情：adata(多源融合) → 东方财富 双通道
3. 个股K线：adata → 东方财富 双通道
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

from screener.utils import random_headers
from screener.sector import fetch_top_sectors_by_gain

logger = logging.getLogger("stock_selector.sector_leader")

_MIN_DAILY_AMOUNT = 1e8
_MIN_PRICE = 3.0


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v) if v is not None and v != "-" else default
    except (ValueError, TypeError):
        return default


# ═══════════════════════════════════════════════════════
# 1. 涨停板数据（三通道降级）
# ═══════════════════════════════════════════════════════

def _limit_up_akshare() -> Optional[List[Dict]]:
    """主源: akshare 涨停板池"""
    try:
        import akshare as ak
        today = datetime.today().strftime("%Y%m%d")
        df = ak.stock_zt_pool_em(date=today)
        if df is not None and not df.empty:
            rows = []
            for _, r in df.iterrows():
                rows.append({
                    "code": str(r.get("代码", "")),
                    "name": str(r.get("名称", "")),
                    "sector": str(r.get("所属行业", "")),
                })
            return rows
    except Exception as e:
        logger.debug(f"akshare涨停板失败: {e}")
    return None


def _limit_up_pywencai() -> Optional[List[Dict]]:
    """备源: pywencai（同花顺问财，自然语言查询"今日涨停股"）"""
    try:
        import pywencai
        today = datetime.today().strftime("%Y%m%d")
        df = pywencai.get(query=f"{today}日 涨停股 所属行业")
        if df is not None and not df.empty:
            rows = []
            for _, r in df.iterrows():
                code = str(r.get("code", r.get("股票代码", "")))
                name = str(r.get("股票简称", r.get("股票名称", "")))
                if not code or not name:
                    continue
                rows.append({
                    "code": code,
                    "name": name,
                    "sector": str(r.get("所属行业", r.get("行业", ""))),
                })
            if rows:
                return rows
    except Exception as e:
        logger.debug(f"pywencai涨停板失败: {e}")
    return None


def _limit_up_eastmoney() -> Optional[List[Dict]]:
    """兜底: 东方财富涨停板HTTP"""
    try:
        url = "https://push2ex.eastmoney.com/getTopicZTPool"
        params = {
            "ut": "7eea3edcaed734bece9cbfce244654ed",
            "PageIndex": "1", "PageSize": "500",
            "sort": "fbt:asc", "date": datetime.today().strftime("%Y%m%d"),
        }
        resp = requests.get(url, params=params, headers=random_headers(), timeout=15)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("pool", []) or []
        rows = []
        for i in items:
            rows.append({
                "code": str(i.get("c", "")),
                "name": str(i.get("n", "")),
                "sector": str(i.get("hybk", "")),
            })
        return rows
    except Exception as e:
        logger.debug(f"东方财富涨停板失败: {e}")
    return None


def fetch_limit_up_board() -> List[Dict]:
    """获取今日涨停板（akshare → pywencai → 东方财富）"""
    # 主源
    rows = _limit_up_akshare()
    if rows:
        logger.info(f"[涨停板] akshare: {len(rows)} 只")
        return rows

    # 备源: pywencai（同花顺问财，不依赖东方财富）
    logger.info("[涨停板] akshare失败 → 尝试 pywencai")
    rows = _limit_up_pywencai()
    if rows:
        logger.info(f"[涨停板] pywencai: {len(rows)} 只")
        return rows

    # 兜底: 东方财富
    logger.info("[涨停板] pywencai失败 → 降级东方财富")
    rows = _limit_up_eastmoney()
    logger.info(f"[涨停板] 东方财富: {len(rows)} 只")
    return rows


def aggregate_limit_up_by_sector(limit_up_list: List[Dict]) -> Dict[str, int]:
    sector_counts: Dict[str, int] = {}
    for stock in limit_up_list:
        s = stock.get("sector", "").strip()
        if not s or s in ("无", "其它", "null"):
            continue
        sector_counts[s] = sector_counts.get(s, 0) + 1
    return sector_counts


# ═══════════════════════════════════════════════════════
# 2. 板块详情（东方财富 + adata 概念板块）
# ═══════════════════════════════════════════════════════

def _sector_detail_eastmoney() -> List[Dict]:
    """东方财富行业板块HTTP（主源，aks与limit-up同源）"""
    rows = []
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        for page in [1, 2]:
            params = {
                "pn": str(page), "pz": "100", "po": "1", "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2", "invt": "2", "fid": "f3",
                "fs": "m:90+t:2+f:!50",
                "fields": "f12,f14,f3,f6,f104",
            }
            resp = requests.get(url, params=params, headers=random_headers(), timeout=15)
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("diff", []) or []
            if not items:
                break
            for i in items:
                rows.append({
                    "code": str(i.get("f12", "")),
                    "name": str(i.get("f14", "")),
                    "gain_pct": _safe_float(i.get("f3")),
                    "amount_yi": round(_safe_float(i.get("f6")) / 1e8, 2),
                    "up_count": int(_safe_float(i.get("f104", 0))),
                })
            if len(items) < 100:
                break
    except Exception as e:
        logger.debug(f"东方财富板块详情失败: {e}")
    return rows


# ═══════════════════════════════════════════════════════
# 3. 主线板块识别
# ═══════════════════════════════════════════════════════

def _fuzzy_match_sector(zt_name: str, em_names: List[str]) -> Optional[str]:
    """模糊匹配 akshare涨停板板块名 → 东方财富板块名"""
    from difflib import SequenceMatcher
    best_score, best_name = 0, None
    zt_clean = zt_name.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    for em in em_names:
        em_clean = em.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # 子串匹配优先
        if zt_clean in em_clean or em_clean in zt_clean:
            return em
        score = SequenceMatcher(None, zt_clean, em_clean).ratio()
        if score > best_score:
            best_score, best_name = score, em
    return best_name if best_score >= 0.60 else None


def identify_leading_sectors(top_n: int = 3) -> List[Dict]:
    """
    识别主线板块（以东财板块成交额+涨幅为主，涨停数为加分项）

    策略：东财板块数据可靠带code → 基础排序（成交额70%+涨幅30%）
          涨停数作为加分项（模糊匹配akshare板块名），但匹配不到不影响入选
    """
    limit_up_list = fetch_limit_up_board()
    sector_details = _sector_detail_eastmoney()

    if not sector_details:
        logger.warning("无法获取板块详情，仅用涨幅排名")
        top_sectors = fetch_top_sectors_by_gain(top_n)
        return [
            {"rank": i + 1, "name": s["name"], "code": s.get("code", ""),
             "score": 0, "limit_up_count": 0,
             "gain_pct": s.get("gain_pct", 0),
             "amount_yi": s.get("amount_yi", 0),
             "leader_stocks": []}
            for i, s in enumerate(top_sectors)
        ]

    em_names = [s["name"] for s in sector_details]

    # 模糊匹配：akshare涨停板块名 → 东财板块名
    zt_by_em: Dict[str, int] = {}
    raw_zt: Dict[str, int] = {}
    matched_count = 0
    unmatched_samples = []
    for stock in limit_up_list:
        s = stock.get("sector", "").strip()
        if not s or s in ("无", "其它", "null"):
            continue
        raw_zt[s] = raw_zt.get(s, 0) + 1
        matched = _fuzzy_match_sector(s, em_names)
        if matched:
            zt_by_em[matched] = zt_by_em.get(matched, 0) + 1
            matched_count += 1
        elif len(unmatched_samples) < 5:
            unmatched_samples.append(s)

    total_limit_up = len(limit_up_list)
    logger.info(
        f"[涨停映射] {total_limit_up}只涨停 → {matched_count}只匹配到东财板块 "
        f"({len(zt_by_em)}个板块), {len(raw_zt)}个原始板块名"
    )
    if unmatched_samples:
        logger.info(f"[涨停映射] 未匹配样本: {unmatched_samples}")

    # 基础排序：成交额(70%) + 涨幅(30%)，涨停数为加分项
    amt_vals = [s["amount_yi"] for s in sector_details if s["amount_yi"] > 0]
    gain_vals = [s["gain_pct"] for s in sector_details]

    max_amt = max(amt_vals) if amt_vals else 1
    max_gain = max(max(gain_vals) if gain_vals else 1, 1)
    max_zt = max(zt_by_em.values()) if zt_by_em else 1

    scored = []
    for s in sector_details:
        code = s.get("code", "")
        if not code:
            continue

        zt = zt_by_em.get(s["name"], 0)
        amt = s["amount_yi"]
        gain = s["gain_pct"]

        # 基础分 = 成交额(55%) + 涨幅(20%) + 涨停加分(25%)
        base = (amt / max_amt * 55) + (gain / max_gain * 20)
        bonus = (zt / max_zt * 25) if zt > 0 else 0
        score = base + bonus

        scored.append({
            "name": s["name"], "code": code,
            "score": round(score, 1),
            "limit_up_count": zt,
            "gain_pct": round(gain, 2),
            "amount_yi": round(amt, 2),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    for i, s in enumerate(scored[:top_n]):
        s["rank"] = i + 1

    top = scored[:top_n]
    logger.info(
        f"[主线板块] Top{top_n}: "
        + " | ".join(f"{s['rank']}.{s['name']}({s['score']}分,{s['limit_up_count']}涨停,{s['amount_yi']}亿)" for s in top)
    )
    return top


# ═══════════════════════════════════════════════════════
# 4. 板块成分股 + 龙头选股（adata → 东方财富）
# ═══════════════════════════════════════════════════════

def _fetch_sector_stocks_eastmoney(sector_code: str) -> List[Dict]:
    """东方财富板块成分股（按成交额降序）"""
    stocks = []
    if not sector_code:
        return stocks
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        for page in [1, 2]:
            params = {
                "pn": str(page), "pz": "100", "po": "1", "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2", "invt": "2", "fid": "f6",
                "fs": f"b:{sector_code}+f:!50",
                "fields": "f12,f14,f2,f3,f6,f8,f15,f16,f17,f18",
            }
            resp = requests.get(url, params=params, headers=random_headers(), timeout=15)
            resp.raise_for_status()
            items = resp.json().get("data", {}).get("diff", []) or []
            if not items:
                break
            for i in items:
                code = str(i.get("f12", ""))
                name = str(i.get("f14", ""))
                if not code or not name or "*ST" in name or "ST" in name:
                    continue
                stocks.append({
                    "code": code, "name": name,
                    "price": _safe_float(i.get("f2")),
                    "gain_pct": _safe_float(i.get("f3")),
                    "amount_yi": round(_safe_float(i.get("f6")) / 1e8, 2),
                    "turnover_pct": _safe_float(i.get("f8")),
                    "high": _safe_float(i.get("f15")),
                    "low": _safe_float(i.get("f16")),
                    "open": _safe_float(i.get("f17")),
                    "volume_ratio": _safe_float(i.get("f18"), 1.0),
                })
            if len(items) < 100:
                break
    except Exception as e:
        logger.debug(f"东方财富成分股失败 {sector_code}: {e}")
    return stocks


def _fetch_stock_kline_adata(code: str, days: int = 30) -> Optional[pd.DataFrame]:
    """主源: adata 个股日K（多源融合）"""
    try:
        import adata
        start = (datetime.today() - timedelta(days=days + 10)).strftime("%Y-%m-%d")
        df = adata.stock.market.get_market(stock_code=code, k_type=1, start_date=start)
        if df is not None and not df.empty:
            col_map = {}
            for col in df.columns:
                cl = col.lower()
                if "date" in cl or "日期" in col:
                    col_map[col] = "date"
                elif "close" in cl or "收" in col:
                    col_map[col] = "close"
                elif "volume" in cl or "量" in col:
                    col_map[col] = "volume"
            df = df.rename(columns=col_map)
            keep = ["date", "close", "volume"]
            if not all(c in df.columns for c in ["date", "close"]):
                return None
            df["date"] = pd.to_datetime(df["date"])
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            if "volume" in df.columns:
                df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            else:
                df["volume"] = 0
            df = df.dropna(subset=["date", "close"]).sort_values("date").reset_index(drop=True)
            if len(df) >= 10:
                return df
    except Exception as e:
        logger.debug(f"adata K线 {code} 失败: {e}")
    return None


def _fetch_stock_kline_eastmoney(code: str, days: int = 30) -> Optional[pd.DataFrame]:
    """备源: 东方财富个股日K"""
    try:
        market = 1 if code.startswith(("6", "5", "9")) else 0
        secid = f"{market}.{code}"
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": secid,
            "ut": "fa5fd1943c7b386f172d6893dbfd10b4",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "klt": "101", "fqt": "1",
            "end": "20500101", "lmt": str(days + 10),
        }
        resp = requests.get(url, params=params, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        klines = resp.json().get("data", {}).get("klines", []) or []
        if not klines:
            return None
        rows = []
        for line in klines:
            parts = line.split(",")
            rows.append({"date": parts[0], "close": float(parts[2]), "volume": float(parts[5])})
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception:
        return None


def _fetch_stock_kline(code: str, days: int = 30) -> Optional[pd.DataFrame]:
    """个股日K: adata → 东方财富 双通道"""
    df = _fetch_stock_kline_adata(code, days)
    if df is not None:
        return df
    logger.debug(f"adata K线 {code} 失败 → 降级东方财富")
    return _fetch_stock_kline_eastmoney(code, days)


def _check_ma_position(df: pd.DataFrame) -> Dict:
    """检查MA5/MA10和缩量回调信号"""
    close = df["close"]
    vol = df["volume"]

    above_ma5 = bool(close.iloc[-1] > close.rolling(5).mean().iloc[-1]) if len(close) >= 5 else False
    above_ma10 = bool(close.iloc[-1] > close.rolling(10).mean().iloc[-1]) if len(close) >= 10 else False

    vol_shrinking = False
    pullback = False
    if len(vol) >= 5 and len(close) >= 5:
        vol_3d = float(vol.iloc[-3:].mean())
        vol_5d_prev = float(vol.iloc[-8:-3].mean())
        if vol_5d_prev > 0:
            vol_shrinking = bool(vol_3d < vol_5d_prev * 0.90)
        pullback = bool(float(close.iloc[-1]) < float(close.iloc[-3]))

    consecutive_up = 0
    for i in range(len(close) - 1, 0, -1):
        if close.iloc[i] > close.iloc[i - 1]:
            consecutive_up += 1
        else:
            break

    return {
        "above_ma5": above_ma5, "above_ma10": above_ma10,
        "vol_shrinking": vol_shrinking, "pullback": pullback,
        "consecutive_up": consecutive_up,
        "close": round(float(close.iloc[-1]), 2),
        "ma5": round(float(close.rolling(5).mean().iloc[-1]), 2) if len(close) >= 5 else 0,
        "ma10": round(float(close.rolling(10).mean().iloc[-1]), 2) if len(close) >= 10 else 0,
    }


# ═══════════════════════════════════════════════════════
# 5. 龙头选股入口
# ═══════════════════════════════════════════════════════

def pick_leader_stocks(sector_name: str, sector_code: str, top_n: int = 3) -> List[Dict]:
    """
    板块内选龙头股：按成交额排序 → K线均线检查 → 三档信号
    """
    stocks = _fetch_sector_stocks_eastmoney(sector_code)
    if not stocks:
        logger.warning(f"[龙头选股] {sector_name} 无成分股数据")
        return []

    candidates = []
    for s in stocks:
        if s["price"] < _MIN_PRICE or s["amount_yi"] < 1.0:
            continue

        df = _fetch_stock_kline(s["code"], days=30)
        if df is None or len(df) < 10:
            continue

        ma_info = _check_ma_position(df)
        s.update(ma_info)

        reasons, warnings = [], []

        if ma_info["above_ma5"] and ma_info["above_ma10"]:
            reasons.append("站稳5/10日线")
        elif ma_info["above_ma5"]:
            reasons.append("站上5日线")
            warnings.append("未站上10日线")
        else:
            warnings.append("跌破5日线")

        if ma_info["pullback"] and ma_info["vol_shrinking"]:
            reasons.append("缩量回调")
        elif not ma_info["pullback"] and s["gain_pct"] > 0:
            if s["volume_ratio"] > 1.5:
                warnings.append("放量追涨")
            else:
                reasons.append("温和上涨")

        if ma_info["consecutive_up"] >= 5:
            warnings.append(f"连涨{ma_info['consecutive_up']}天")

        if ma_info["vol_shrinking"] and not ma_info["pullback"]:
            reasons.append("缩量整理")

        if len(warnings) >= 3:
            signal = "回避"
        elif len(warnings) >= 1:
            signal = "观望"
        elif len(reasons) >= 2:
            signal = "可介入"
        else:
            signal = "观望"

        s["signal"] = signal
        s["buy_reasons"] = reasons
        s["risk_warnings"] = warnings
        s["signal_reason"] = "；".join(reasons) if signal == "可介入" else "⚠️ " + "；".join(warnings)
        candidates.append(s)

    candidates.sort(key=lambda x: (0 if x["signal"] == "可介入" else 1, -x["amount_yi"]))
    leaders = candidates[:top_n]
    for i, s in enumerate(leaders):
        s["leader_rank"] = i + 1

    if leaders:
        logger.info(
            f"[龙头选股] {sector_name}: "
            + " | ".join(f"{s['name']}({s['signal']})" for s in leaders)
        )
    else:
        logger.warning(f"[龙头选股] {sector_name}: 无符合条件的标的")

    return leaders
