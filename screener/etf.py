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
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

from screener.calendar import resample_weekly, get_current_week_info
from screener.utils import random_headers

logger = logging.getLogger("stock_selector.etf")

# BaoStock 全局 session 不是线程安全的，必须串行化
_baostock_lock = threading.Lock()


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

        # 只保留交易所交易的ETF代码
        _VALID_ETF_PREFIX = ("510", "511", "512", "513", "515", "516", "517", "518", "588", "159")

        rows = []
        for i in all_items:
            code = str(i.get("f12", ""))
            if not code or not code.startswith(_VALID_ETF_PREFIX):
                continue
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
    """通过akshare获取ETF列表（备源），仅保留交易所交易代码"""
    try:
        import akshare as ak
        df = ak.fund_info_index_em(symbol="全部", indicator="被动指数型")
        if df is not None and not df.empty:
            df = df.rename(columns={
                "基金代码": "code",
                "基金名称": "name",
                "跟踪标的": "index_name",
            })
            _VALID_ETF_PREFIX = ("510", "511", "512", "513", "515", "516", "517", "518", "588", "159")
            df = df[df["code"].astype(str).str.startswith(_VALID_ETF_PREFIX)]
            logger.info(f"[etf] akshare被动指数型ETF: {len(df)} 个")
            return df[["code", "name", "index_name"]]
    except Exception as e:
        logger.debug(f"[etf] fund_info_index_em失败: {e}")
    return None


def _extract_index_key(name: str) -> str:
    """从ETF名称中提取指数关键字用于去重"""
    s = re.sub(r'ETF[A-Za-z\u4e00-\u9fff]*$', '', name, flags=re.IGNORECASE)
    s = re.sub(r'指数$', '', s)
    m = re.match(r'^中证(.+)$', s)
    if m:
        rest = m.group(1)
        if re.match(r'^[A-Za-z\u4e00-\u9fff]', rest):
            s = rest  # "中证A500" -> "A500"
    s = re.sub(r'指数[AC]$', '', s)
    s = s.strip()
    return s if s else name


def deduplicate_by_index(etf_df: pd.DataFrame) -> pd.DataFrame:
    """按指数关键字去重：同一指数只保留成交额最大的ETF"""
    etf_df = etf_df.copy()
    etf_df["index_key"] = etf_df["name"].apply(_extract_index_key)
    etf_df = etf_df.sort_values("amount", ascending=False)
    etf_dedup = etf_df.groupby("index_key", sort=False).first().reset_index()
    logger.info(f"[etf] 去重后: {len(etf_dedup)} 只ETF（每指数一只，原始{len(etf_df)}只）")
    return etf_dedup


def _etf_secid(code: str) -> str:
    return f"1.{code}" if code.startswith("5") else f"0.{code}"


def _etf_prefix(code: str) -> str:
    return "sh" if code.startswith("5") else "sz"


_COLS = ["date", "open", "high", "low", "close", "volume", "amount"]


def _to_etf_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """标准化并校验ETF DataFrame，少于325条(约65周)视为无效"""
    if df is None or df.empty:
        return None
    df = df[_COLS].copy()
    df["date"] = pd.to_datetime(df["date"])
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    mask = df["amount"].isna() | (df["amount"] <= 0)
    df.loc[mask, "amount"] = df.loc[mask, "close"] * df.loc[mask, "volume"] * 100
    df = df[df["amount"] > 0]
    df = df.dropna().sort_values("date").reset_index(drop=True)
    return df if len(df) >= 325 else None


def _fetch_etf_browserbase(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    """通过 Browserbase Fetch API 中转请求东方财富 K 线接口"""
    import os
    import subprocess
    import json as _json

    api_key = os.environ.get("BROWSERBASE_API_KEY", "").strip()
    if not api_key:
        return None

    start_date = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")
    target_url = (
        "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        f"?secid={_etf_secid(code)}"
        "&fields1=f1,f2,f3,f4,f5,f6"
        "&fields2=f51,f52,f53,f54,f55,f56,f57"
        "&ut=fa5fd1943c7b386f172d6893dbfba10b"
        "&klt=101&fqt=1&lmt=1000"
        f"&beg={start_date}&end=20991231"
    )
    payload = _json.dumps({"url": target_url, "allowRedirects": True})

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                "https://api.browserbase.com/v1/fetch",
                "-H", "Content-Type: application/json",
                "-H", f"X-BB-API-Key: {api_key}",
                "-d", payload,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 or not result.stdout:
            return None

        outer = _json.loads(result.stdout)
        if outer.get("statusCode", 0) != 200:
            return None

        inner = _json.loads(outer.get("content", "{}"))
        klines = (inner.get("data") or {}).get("klines", [])
        if not klines:
            return None

        rows = []
        for k in klines:
            p = k.split(",")
            if len(p) < 7:
                continue
            rows.append({
                "date": p[0], "open": p[1], "close": p[2],
                "high": p[3], "low": p[4], "volume": p[5], "amount": p[6],
            })
        return _to_etf_df(pd.DataFrame(rows)[_COLS])
    except Exception as e:
        logger.debug(f"[etf/browserbase] {code}: {e}")
    return None


def _fetch_etf_akshare_sina(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    try:
        import akshare as ak
        prefix = _etf_prefix(code)
        symbol = f"{prefix}{code}"
        df = ak.fund_etf_hist_sina(symbol=symbol)
        if df is not None and not df.empty:
            if "amount" not in df.columns:
                df["amount"] = df["close"].astype(float) * df["volume"].astype(float)
            df["date"] = pd.to_datetime(df["date"])
            cutoff = datetime.today() - timedelta(days=days)
            df = df[df["date"] >= cutoff]
            return _to_etf_df(df)
    except Exception as e:
        logger.debug(f"[etf/akshare-sina] {code}: {e}")
    return None


def _fetch_etf_tencent(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    try:
        key = f"{_etf_prefix(code)}{code}"
        url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
               f"?_var=kline_dayqfq&param={key},day,,,640,qfq")
        resp = requests.get(url, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()
        text = text[text.index("{"):]
        import json
        days_data = json.loads(text).get("data", {}).get(key, {}).get("qfqday", [])
        if not days_data:
            return None
        rows = [{
            "date": d[0], "open": d[1], "close": d[2],
            "high": d[3], "low": d[4],
            "volume": float(d[5]) * 100,
            "amount": float(d[2]) * float(d[5]) * 100,
        } for d in days_data]
        return _to_etf_df(pd.DataFrame(rows)[_COLS])
    except Exception as e:
        logger.debug(f"[etf/tencent] {code}: {e}")
    return None


def _fetch_etf_eastmoney(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    try:
        start_date = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": _etf_secid(code),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
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
        return _to_etf_df(pd.DataFrame(rows)[_COLS])
    except Exception as e:
        logger.debug(f"[etf/eastmoney] {code}: {e}")
    return None


_ts_pro = None

def _init_tushare(token: str) -> bool:
    global _ts_pro
    if _ts_pro is not None:
        return True
    if not token:
        return False
    try:
        import tushare as ts
        ts.set_token(token)
        _ts_pro = ts.pro_api()
        return True
    except Exception as e:
        logger.debug(f"[etf/tushare] 初始化失败: {e}")
    return False


def _fetch_etf_tushare(code: str, token: str, days: int = 730) -> Optional[pd.DataFrame]:
    if not _init_tushare(token):
        return None
    try:
        ts_code = f"{code}.SH" if code.startswith("5") else f"{code}.SZ"
        start = (datetime.today() - timedelta(days=days)).strftime("%Y%m%d")
        df = _ts_pro.fund_daily(ts_code=ts_code, start_date=start)
        if df is None or df.empty:
            return None
        df = df.rename(columns={"trade_date": "date", "vol": "volume"})
        df["amount"] = df["amount"] * 1000
        return _to_etf_df(df[_COLS])
    except Exception as e:
        logger.debug(f"[etf/tushare] {code}: {e}")
    return None


def _fetch_etf_mairui(code: str, token: str, days: int = 730) -> Optional[pd.DataFrame]:
    if not token:
        return None
    try:
        url = f"http://api.mairui.club/hszbl/fsjy/{code}/dn/{token}"
        resp = requests.get(url, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        raw = resp.json()
        if not raw:
            return None
        rows = [{
            "date": r["d"], "open": r["o"], "high": r["h"], "low": r["l"],
            "close": r["c"], "volume": r["v"],
            "amount": r.get("e", float(r["c"]) * float(r["v"])),
        } for r in raw]
        df = pd.DataFrame(rows)[_COLS]
        df["date"] = pd.to_datetime(df["date"])
        return _to_etf_df(df[df["date"] >= datetime.today() - timedelta(days=days)])
    except Exception as e:
        logger.debug(f"[etf/mairui] {code}: {e}")
    return None


def _fetch_etf_baostock(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    with _baostock_lock:
        try:
            import baostock as bs
            lg = bs.login()
            if lg.error_code != "0":
                return None
            start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
            prefix = _etf_prefix(code)
            rs = bs.query_history_k_data_plus(
                f"{prefix}.{code}",
                "date,open,high,low,close,volume,amount",
                start_date=start, frequency="d", adjustflag="2",
            )
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            bs.logout()
            if not rows:
                return None
            return _to_etf_df(pd.DataFrame(rows, columns=_COLS))
        except Exception as e:
            logger.debug(f"[etf/baostock] {code}: {e}")
        return None


def _fetch_etf_akshare_em(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    import akshare as ak
    try:
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low",
                "成交量": "volume", "成交额": "amount",
            })
            return _to_etf_df(df)
    except Exception as e:
        logger.debug(f"[etf/akshare-em] {code}: {e}")
    return None


def _fetch_etf_sina(code: str, days: int = 730) -> Optional[pd.DataFrame]:
    try:
        url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
               "/CN_MarketData.getKLineData")
        params = {"symbol": f"{_etf_prefix(code)}{code}", "scale": 240, "ma": "no", "datalen": 730}
        resp = requests.get(url, params=params, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        import json
        raw = json.loads(resp.text)
        if not raw:
            return None
        rows = [{
            "date": r["day"], "open": r["open"], "high": r["high"],
            "low": r["low"], "close": r["close"], "volume": r["volume"],
            "amount": float(r.get("amount", 0)) * 10000,
        } for r in raw]
        return _to_etf_df(pd.DataFrame(rows)[_COLS])
    except Exception as e:
        logger.debug(f"[etf/sina] {code}: {e}")
    return None


def fetch_etf_kline(symbol: str, days: int = 730, cfg: dict = None) -> Optional[pd.DataFrame]:
    """获取ETF日K线数据（9源轮换）"""
    ds = (cfg or {}).get("datasources", {})
    tushare_token = ds.get("tushare_token", "")
    mairui_token = ds.get("mairui_token", "")

    mt_sources = [
        ("browserbase",  lambda: _fetch_etf_browserbase(symbol, days)),
        ("akshare-sina", lambda: _fetch_etf_akshare_sina(symbol, days)),
        ("tencent",      lambda: _fetch_etf_tencent(symbol, days)),
        ("eastmoney",    lambda: _fetch_etf_eastmoney(symbol, days)),
        ("tushare",      lambda: _fetch_etf_tushare(symbol, tushare_token, days)),
        ("mairui",       lambda: _fetch_etf_mairui(symbol, mairui_token, days)),
    ]
    st_sources = [
        ("baostock",     lambda: _fetch_etf_baostock(symbol, days)),
        ("akshare-em",   lambda: _fetch_etf_akshare_em(symbol, days)),
        ("sina",         lambda: _fetch_etf_sina(symbol, days)),
    ]

    import time, random as _random
    delay_min = (cfg or {}).get("request", {}).get("delay_min", 0.2)
    delay_max = (cfg or {}).get("request", {}).get("delay_max", 0.5)

    now = datetime.now()
    after_close = now.weekday() >= 5 or (now.weekday() < 5 and now.hour >= 16)
    if after_close:
        for lock_name, lock_fn in [
            ("browserbase",  lambda: _fetch_etf_browserbase(symbol, days)),
            ("akshare-sina", lambda: _fetch_etf_akshare_sina(symbol, days)),
        ]:
            try:
                time.sleep(_random.uniform(delay_min, delay_max))
                df = lock_fn()
                if df is not None and not df.empty:
                    return df
            except Exception:
                continue

    for name, fn in mt_sources + st_sources:
        try:
            time.sleep(_random.uniform(delay_min, delay_max))
            df = fn()
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return None


_ETF_WHITELIST: List[tuple] = [
    ("510050", "上证50ETF"), ("510300", "沪深300ETF"), ("510500", "中证500ETF"),
    ("512100", "中证1000ETF"), ("159915", "创业板ETF"), ("588000", "科创50ETF"),
    ("159901", "深证100ETF"), ("159949", "创业板50ETF"), ("510180", "上证180ETF"),
    ("512480", "半导体ETF"), ("159995", "芯片ETF"), ("159819", "人工智能ETF"),
    ("513310", "中韩半导体ETF"), ("159896", "云计算ETF"), ("159892", "计算机ETF"),
    ("515020", "新能源车ETF"), ("512760", "纳指科技ETF"), ("512170", "医疗ETF"),
    ("512010", "医药ETF"), ("515120", "医疗器械ETF"), ("159987", "创新药ETF"),
    ("159928", "主要消费ETF"), ("512690", "白酒ETF"), ("515170", "食品饮料ETF"),
    ("159176", "家电ETF"), ("512880", "证券ETF"), ("515280", "银行ETF"),
    ("512070", "非银金融ETF"), ("512400", "有色金属ETF"), ("516970", "煤炭ETF"),
    ("159199", "石油ETF"), ("516020", "化工ETF"), ("512660", "军工ETF"),
    ("159227", "航空航天ETF"), ("510880", "红利ETF"), ("512890", "红利低波ETF"),
    ("515450", "红利低波50ETF"), ("159905", "深红利ETF"), ("513180", "恒生科技ETF"),
    ("513050", "中概互联ETF"), ("513330", "恒生互联网ETF"), ("513120", "港股创新药ETF"),
    ("513500", "标普500ETF"), ("159941", "纳指ETF"), ("513880", "日经225ETF"),
    ("513630", "港股红利ETF"), ("518880", "黄金ETF"), ("512980", "传媒ETF"),
    ("159856", "软件ETF"), ("159857", "光伏ETF"), ("159869", "养殖ETF"),
    ("159825", "农业ETF"),
]


def _build_etf_df_from_whitelist() -> pd.DataFrame:
    rows = [{"code": code, "name": name, "price": 0.0, "gain_pct": 0.0, "amount": 0.0}
            for code, name in _ETF_WHITELIST]
    df = pd.DataFrame(rows)
    df["index_key"] = df["name"].apply(_extract_index_key)
    return df


def filter_etf_weekly(cfg: dict) -> List[Dict]:
    """用与板块相同的周K参数筛选ETF"""
    scfg = cfg.get("screener", {})
    weekly_ma = scfg.get("weekly_ma", 25)
    vol_short = scfg.get("vol_ma_short", 5)
    vol_long = scfg.get("vol_ma_long", 60)
    dev_min = scfg.get("vol_deviation_min", -0.03)
    dev_max = scfg.get("vol_deviation_max", 0.07)
    min_amount = scfg.get("min_daily_amount", 300000000)
    mode = scfg.get("weekly_mode", "realtime")

    etf_spot = fetch_etf_spot_em(min_amount=min_amount)
    if etf_spot is not None and not etf_spot.empty:
        etf_df = deduplicate_by_index(etf_spot)
    else:
        logger.warning("[etf] 接口失败，使用内置白名单")
        etf_df = _build_etf_df_from_whitelist()

    if etf_df.empty:
        return []

    passed = []
    for idx, row in etf_df.iterrows():
        code = str(row["code"])
        name = str(row["name"])

        df_daily = fetch_etf_kline(code, cfg=cfg)
        if df_daily is None or len(df_daily) < 325:
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

        passed.append({
            "code": code,
            "name": name,
            "index_name": str(row.get("index_key", "")),
            "price": round(latest_price, 4),
            "vol_deviation_pct": round(deviation * 100, 2),
            "daily_amount_yi": round(latest_amount / 1e8, 2),
            "ma25_weekly": round(ma25_w.iloc[-1], 4),
            "etf_trend": "放量上行" if deviation > 0.03 else "温和上行",
        })

    logger.info(f"[etf] ETF筛选完成: {len(passed)} 个通过")
    return passed
