"""
datasources.py
==============
数据源设计原则：
- 股票列表：baostock 单线程获取（最稳定）
- 实时快照：东方财富 HTTP（预筛价格/成交额）
- 日K数据：东方财富为主力（多线程安全），新浪/腾讯备用，baostock/akshare最后兜底（串行）

多线程安全说明：
  东方财富/新浪/腾讯/tushare/mairui  ✅ 纯HTTP无状态，多线程安全
  baostock                           ❌ 全局session，多线程会串数据，只用于单线程场景
  akshare                            ⚠️ 底层不稳定，放最后兜底
"""

import time
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import json

import pandas as pd
import requests

from screener.utils import random_headers

logger = logging.getLogger("stock_selector.datasources")

_COLS = ["date", "open", "high", "low", "close", "volume", "amount"]


def _start_date() -> str:
    return (datetime.today() - timedelta(days=730)).strftime("%Y%m%d")


def _to_df(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """标准化并校验 DataFrame，少于200条视为无效"""
    if df is None or df.empty:
        return None
    df = df[_COLS].copy()
    df["date"] = pd.to_datetime(df["date"])
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # 验证成交额数据：确保amount为正数且合理
    df = df[df["amount"] > 0]
    df = df.dropna().sort_values("date").reset_index(drop=True)
    return df if len(df) >= 200 else None


# ─────────────────────────────────────────────────────────────
# 实时行情快照（静态预筛用）
# ─────────────────────────────────────────────────────────────
def fetch_spot_data(cfg: dict) -> Optional[pd.DataFrame]:
    """
    一次性获取全市场实时行情，返回 DataFrame(columns=["code","price","amount"])
    失败返回 None，主流程会降级为逐只判断
    """
    # 1. akshare 东方财富实时行情
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        df = df[["代码", "最新价", "成交额"]].rename(columns={
            "代码": "code", "最新价": "price", "成交额": "amount"
        })
        df["price"]  = pd.to_numeric(df["price"],  errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df = df.dropna()
        if not df.empty:
            logger.info(f"[spot/akshare] 实时快照: {len(df)} 只")
            return df
    except Exception as e:
        logger.debug(f"[spot/akshare] 失败: {e}")

    # 2. 东方财富直接HTTP
    try:
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "10000", "po": "1", "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2", "invt": "2", "fid": "f3",
            "fs": "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23",
            "fields": "f12,f2,f6",
        }
        resp = requests.get(url, params=params, headers=random_headers(), timeout=15)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("diff", [])
        if items:
            df = pd.DataFrame([{
                "code": i["f12"], "price": i["f2"], "amount": i["f6"]
            } for i in items])
            df["price"]  = pd.to_numeric(df["price"],  errors="coerce")
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
            df = df.dropna()
            if not df.empty:
                logger.info(f"[spot/eastmoney] 实时快照: {len(df)} 只")
                return df
    except Exception as e:
        logger.warning(f"[spot/eastmoney] 失败: {e}")

    # 3. 备选方案：直接从日K数据中获取最新成交额
    try:
        # 这里可以实现一个简单的备选方案，从日K数据中获取最新成交额
        # 但考虑到性能问题，这里暂时跳过
        logger.info("[spot/backup] 尝试从日K数据获取成交额")
    except Exception as e:
        logger.warning(f"[spot/backup] 失败: {e}")

    logger.warning("实时快照获取失败，跳过预筛，后续逐只判断价格/成交额")
    return None


# ─────────────────────────────────────────────────────────────
# 股票列表（baostock 单线程，过滤退市）
# ─────────────────────────────────────────────────────────────
def fetch_stock_list(cfg: dict) -> Optional[pd.DataFrame]:
    """
    返回 DataFrame(columns=["code","name","list_date"])
    只返回当前在市普通A股
    """
    ds = cfg.get("datasources", {})

    # 1. baostock — 单线程最稳定，明确过滤退市
    try:
        import baostock as bs
        bs.login()
        rs = bs.query_stock_basic()
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()
        df = pd.DataFrame(rows, columns=rs.fields)
        df = df[(df["type"] == "1") & (df["status"] == "1")]
        df["code"] = df["code"].str[-6:]
        df = df.rename(columns={"code_name": "name", "ipoDate": "list_date"})[
            ["code", "name", "list_date"]
        ]
        df["list_date"] = df["list_date"].str.replace("-", "")
        if not df.empty:
            logger.info(f"[baostock] 股票列表: {len(df)} 只（已过滤退市）")
            return df
    except Exception as e:
        logger.warning(f"[baostock] 股票列表失败: {e}")

    # 2. akshare 兜底
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        df.columns = ["code", "name"]
        try:
            info = ak.stock_zh_a_spot_em()[["代码", "上市时间"]].rename(
                columns={"代码": "code", "上市时间": "list_date"}
            )
            info["list_date"] = info["list_date"].astype(str).str.replace("-", "")
            df = df.merge(info, on="code", how="left")
        except Exception:
            df["list_date"] = "20000101"
        if not df.empty:
            logger.info(f"[akshare] 股票列表: {len(df)} 只")
            return df
    except Exception as e:
        logger.warning(f"[akshare] 股票列表失败: {e}")

    # 3. tushare
    token = ds.get("tushare_token", "")
    if token and _init_tushare(token):
        try:
            df = _ts_pro.stock_basic(exchange="", list_status="L",
                                     fields="ts_code,name,list_date")
            df["code"] = df["ts_code"].str[:6]
            df = df[["code", "name", "list_date"]]
            if not df.empty:
                logger.info(f"[tushare] 股票列表: {len(df)} 只")
                return df
        except Exception as e:
            logger.warning(f"[tushare] 股票列表失败: {e}")

    logger.error("所有数据源均无法获取股票列表")
    return None


# ─────────────────────────────────────────────────────────────
# 1. 东方财富（主力，多线程安全）
# ─────────────────────────────────────────────────────────────
def _em_secid(code: str) -> str:
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def _fetch_eastmoney(code: str) -> Optional[pd.DataFrame]:
    try:
        url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid":   _em_secid(code),
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57",
            "klt": "101", "fqt": "1",
            "beg": _start_date(), "end": "20991231", "lmt": "1000",
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
                "high": p[3], "low":  p[4], "volume": p[5], "amount": p[6],
            })
        return _to_df(pd.DataFrame(rows)[_COLS])
    except Exception as e:
        logger.debug(f"[eastmoney] {code}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 2. 新浪财经（多线程安全）
# ─────────────────────────────────────────────────────────────
def _fetch_sina(code: str) -> Optional[pd.DataFrame]:
    """
    注意：新浪此接口不支持复权参数，返回不复权数据。
    仅作为最后兜底使用，优先级低于东方财富/baostock/腾讯。
    """
    try:
        prefix = "sh" if code.startswith("6") else "sz"
        url = (
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
            "/CN_MarketData.getKLineData"
        )
        params = {"symbol": f"{prefix}{code}", "scale": 240, "ma": "no", "datalen": 730}
        resp = requests.get(url, params=params, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        raw = json.loads(resp.text)
        if not raw:
            return None
        rows = [{
            "date": r["day"], "open": r["open"], "high": r["high"],
            "low": r["low"], "close": r["close"], "volume": r["volume"],
            "amount": float(r.get("amount", 0)) * 10000,
        } for r in raw]
        return _to_df(pd.DataFrame(rows)[_COLS])
    except Exception as e:
        logger.debug(f"[sina] {code}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 3. 腾讯财经（多线程安全，amount 为近似值）
# ─────────────────────────────────────────────────────────────
def _fetch_tencent(code: str) -> Optional[pd.DataFrame]:
    try:
        prefix = "sh" if code.startswith("6") else "sz"
        key = f"{prefix}{code}"
        url = (
            f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            f"?_var=kline_dayqfq&param={key},day,,,640,qfq"
        )
        resp = requests.get(url, headers=random_headers(), timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()
        text = text[text.index("{"):]
        days = json.loads(text).get("data", {}).get(key, {}).get("qfqday", [])
        if not days:
            return None
        rows = [{
            "date": d[0], "open": d[1], "close": d[2],
            "high": d[3], "low": d[4], "volume": float(d[5]) * 100,  # 腾讯财经成交量单位是手，转换为股
            "amount": float(d[2]) * float(d[5]) * 100,  # 腾讯财经成交量单位是手，转换为股
        } for d in days]
        return _to_df(pd.DataFrame(rows)[_COLS])
    except Exception as e:
        logger.debug(f"[tencent] {code}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 4. Tushare（多线程安全，需要token）
# ─────────────────────────────────────────────────────────────
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
        logger.debug(f"[tushare] 初始化失败: {e}")
        return False


def _fetch_tushare(code: str, token: str) -> Optional[pd.DataFrame]:
    if not _init_tushare(token):
        return None
    try:
        ts_code = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
        df = _ts_pro.daily(ts_code=ts_code, start_date=_start_date())
        if df is None or df.empty:
            return None
        df = df.rename(columns={"trade_date": "date", "vol": "volume"})
        df["amount"] = df["amount"] * 1000
        return _to_df(df[_COLS])
    except Exception as e:
        logger.debug(f"[tushare] {code}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 5. 麦蕊（多线程安全，需要token）
# ─────────────────────────────────────────────────────────────
def _fetch_mairui(code: str, token: str) -> Optional[pd.DataFrame]:
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
        return _to_df(df[df["date"] >= datetime.today() - timedelta(days=730)])
    except Exception as e:
        logger.debug(f"[mairui] {code}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 6. BaoStock（线程不安全，只在主线程串行兜底用）
# ─────────────────────────────────────────────────────────────
def _fetch_baostock(code: str) -> Optional[pd.DataFrame]:
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            return None
        s = _start_date()
        start = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        prefix = "sh" if code.startswith("6") else "sz"
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
        return _to_df(pd.DataFrame(rows, columns=_COLS))
    except Exception as e:
        logger.debug(f"[baostock] {code}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 7. AKShare（兜底，GitHub IP 易被封）
# ─────────────────────────────────────────────────────────────
def _fetch_akshare(code: str) -> Optional[pd.DataFrame]:
    try:
        import akshare as ak
        df = ak.stock_zh_a_hist(
            symbol=code, period="daily",
            start_date=_start_date(), adjust="qfq",
        )
        df = df.rename(columns={
            "日期": "date", "开盘": "open", "最高": "high",
            "最低": "low", "收盘": "close",
            "成交量": "volume", "成交额": "amount",
        })
        return _to_df(df)
    except Exception as e:
        logger.debug(f"[akshare] {code}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# 统一入口：多数据源轮换
# 多线程安全的数据源排前面，非安全的排后面串行兜底
# ─────────────────────────────────────────────────────────────
def fetch_daily_kline(code: str, cfg: dict) -> Optional[pd.DataFrame]:
    ds  = cfg.get("datasources", {})
    req = cfg.get("request", {})
    delay_min = req.get("delay_min", 0.2)
    delay_max = req.get("delay_max", 0.5)

    # 优先级说明：
    #   前复权可靠 + 多线程安全 → 排前
    #   前复权可靠 + 非多线程安全 → 中间兜底
    #   不支持复权 → 排最后，万不得已才用
    mt_sources = [
        ("tencent",   lambda: _fetch_tencent(code)),     # 前复权 qfq，多线程安全，amount已修复
        ("eastmoney", lambda: _fetch_eastmoney(code)),   # 前复权 fqt=1，多线程安全
        ("tushare",   lambda: _fetch_tushare(code, ds.get("tushare_token", ""))),  # 前复权
        ("mairui",    lambda: _fetch_mairui(code, ds.get("mairui_token", ""))),    # 前复权
    ]

    # 非多线程安全，前复权可靠，串行兜底
    st_sources = [
        ("baostock",  lambda: _fetch_baostock(code)),    # 前复权 adjustflag=2
        ("akshare",   lambda: _fetch_akshare(code)),     # 前复权 qfq
        ("sina",      lambda: _fetch_sina(code)),         # 不复权，最后兜底
    ]

    for name, fn in mt_sources + st_sources:
        try:
            time.sleep(random.uniform(delay_min, delay_max))
            df = fn()
            if df is not None and not df.empty:
                # 添加code列，方便后续使用
                df["code"] = code
                logger.debug(f"[{name}] {code} ✓")
                return df
        except Exception as e:
            logger.debug(f"[{name}] {code} 异常: {e}")

    logger.warning(f"[all sources failed] {code} 跳过")
    return None


# ─────────────────────────────────────────────────────────────
# 财务数据获取
# ─────────────────────────────────────────────────────────────
def fetch_financial_data(code: str) -> Optional[Dict]:
    """
    获取股票基本面财务数据
    
    Returns:
        dict: 包含 ROE、PE、PB、EPS、营收增长率等数据
    """
    try:
        import akshare as ak
        
        # 1. 尝试获取最新财务指标
        try:
            finance_df = ak.stock_financial_analysis_indicator(code)
            if not finance_df.empty:
                latest = finance_df.iloc[0]
                return {
                    'roe': float(latest.get('净资产收益率(ROE)', 0)),
                    'pe': float(latest.get('市盈率(TTM)', 0)),
                    'pb': float(latest.get('市净率', 0)),
                    'eps': float(latest.get('每股收益', 0)),
                    'revenue_growth': float(latest.get('营业收入同比增长率', 0))
                }
        except Exception as e:
            logger.debug(f"[finance/akshare] 财务指标获取失败: {e}")
        
        # 2. 尝试获取估值数据作为备选
        try:
            valuation_df = ak.stock_zh_a_valuation_indicator(code)
            if not valuation_df.empty:
                latest = valuation_df.iloc[0]
                return {
                    'roe': 0,  # 备选方案可能没有ROE
                    'pe': float(latest.get('市盈率-动态', 0)),
                    'pb': float(latest.get('市净率', 0)),
                    'eps': 0,  # 备选方案可能没有EPS
                    'revenue_growth': 0  # 备选方案可能没有增长率
                }
        except Exception as e:
            logger.debug(f"[finance/akshare] 估值数据获取失败: {e}")
        
    except Exception as e:
        logger.debug(f"[finance] 整体获取失败: {e}")
    
    return None
