# -*- coding: utf-8 -*-
"""
狙击手存储模块 — 基于 GitHub Gist 的7日历史记忆

功能：
- 每日选股结果存入 Gist（按日期key，7天自动清理）
- 累计入选统计：7天内出现N次的票着重提醒
- 读/写失败不阻断主流程

环境变量：
- GIST_PAT: GitHub Personal Access Token（需gist权限）
- GIST_ID: Secret Gist 的 ID

数据格式（watchlist.json）：
{
  "2026-04-22": [
    {"code": "000001", "name": "平安银行", "stars": 4, "score": 72.5},
    ...
  ],
  "2026-04-21": [...]
}
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("stock_selector.sniper")

_GIST_API = "https://api.github.com/gists"
_FILENAME = "watchlist_A.json"
_RETAIN_DAYS = 7

# 滚动股票池（10日窗口）
_POOL_FILENAME = "stock_pool.json"
_POOL_RETAIN_DAYS = 10


def _headers() -> dict:
    pat = os.environ.get("GIST_PAT", "")
    if not pat:
        return {}
    return {"Authorization": f"token {pat}", "Accept": "application/vnd.github.v3+json"}


def _gist_id() -> str:
    return os.environ.get("GIST_ID", "")


def read_gist() -> Dict[str, List[Dict]]:
    """读取Gist数据，失败返回空dict"""
    gid = _gist_id()
    if not gid:
        logger.debug("[sniper] GIST_ID未设置，跳过")
        return {}
    try:
        resp = requests.get(f"{_GIST_API}/{gid}", headers=_headers(), timeout=15)
        resp.raise_for_status()
        content = resp.json().get("files", {}).get(_FILENAME, {}).get("content", "{}")
        data = json.loads(content) if content else {}
        logger.info(f"[sniper] 读取Gist成功，含 {len(data)} 天数据")
        return data
    except Exception as e:
        logger.debug(f"[sniper] 读取Gist失败: {e}")
    return {}


def write_gist(data: Dict[str, List[Dict]]) -> bool:
    """写入Gist数据，失败返回False"""
    gid = _gist_id()
    if not gid:
        logger.debug("[sniper] GIST_ID未设置，跳过写入")
        return False
    try:
        payload = {
            "description": f"stock-selector watchlist (updated {datetime.now().strftime('%Y-%m-%d %H:%M')})",
            "files": {_FILENAME: {"content": json.dumps(data, ensure_ascii=False, indent=2)}}
        }
        resp = requests.patch(f"{_GIST_API}/{gid}", json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        logger.info(f"[sniper] 写入Gist成功，含 {len(data)} 天数据")
        return True
    except Exception as e:
        logger.debug(f"[sniper] 写入Gist失败: {e}")
    return False


def _clean_old(data: Dict[str, List[Dict]], retain_days: int = _RETAIN_DAYS) -> Dict[str, List[Dict]]:
    """清理超过retain_days的旧数据"""
    cutoff = (datetime.now() - timedelta(days=retain_days)).strftime("%Y-%m-%d")
    cleaned = {k: v for k, v in data.items() if k >= cutoff}
    if len(cleaned) < len(data):
        logger.info(f"[sniper] 清理旧数据: {len(data)} → {len(cleaned)} 天")
    return cleaned


def save_daily_results(results: List[Dict]) -> bool:
    """
    保存当日选股结果到Gist

    Args:
        results: 选股结果列表，每项需含 code/name，可选 llm_stars/llm_weighted_score 等

    Returns:
        是否写入成功
    """
    if not results:
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    data = read_gist()

    # 当日结果去重（同code只保留stars最高的）
    today_items = {}
    for r in results:
        code = r.get("code", "")
        if not code:
            continue
        existing = today_items.get(code)
        stars = r.get("llm_stars", 0) or 0
        if existing is None or stars > (existing.get("stars", 0) or 0):
            today_items[code] = {
                "code": code,
                "name": r.get("name", ""),
                "stars": stars,
                "score": r.get("llm_weighted_score") or r.get("weighted_score") or 0,
            }

    data[today] = list(today_items.values())
    data = _clean_old(data)
    return write_gist(data)


def get_multi_day_hits(results: List[Dict]) -> Dict[str, Dict]:
    """
    统计7天内累计入选次数

    Args:
        results: 当日选股结果

    Returns:
        {code: {"count": N, "name": "...", "dates": ["04-22", ...], "max_stars": 5}}
    """
    data = read_gist()
    if not data:
        return {}

    # 当日结果也计入
    today = datetime.now().strftime("%Y-%m-%d")
    today_codes = set()
    for r in results:
        code = r.get("code", "")
        if code:
            today_codes.add(code)

    # 统计每个code在哪些天出现过
    code_days: Dict[str, List[str]] = {}
    code_names: Dict[str, str] = {}
    code_max_stars: Dict[str, int] = {}

    for date_str, items in data.items():
        for item in items:
            code = item.get("code", "")
            if not code:
                continue
            code_days.setdefault(code, []).append(date_str[5:] if len(date_str) >= 10 else date_str)
            code_names[code] = item.get("name", code)
            s = item.get("stars", 0) or 0
            code_max_stars[code] = max(code_max_stars.get(code, 0), s)

    # 当日codes也加入统计
    for code in today_codes:
        if today[5:] not in code_days.get(code, []):
            code_days.setdefault(code, []).append(today[5:])
        for r in results:
            if r.get("code") == code:
                code_names[code] = r.get("name", code)
                s = r.get("llm_stars", 0) or 0
                code_max_stars[code] = max(code_max_stars.get(code, 0), s)

    # 只返回出现2次以上的
    hits = {}
    for code, days_list in code_days.items():
        count = len(set(days_list))
        if count >= 2:
            hits[code] = {
                "count": count,
                "name": code_names.get(code, code),
                "dates": sorted(set(days_list)),
                "max_stars": code_max_stars.get(code, 0),
            }
    return hits


def format_sniper_tag(code: str, hits: Dict[str, Dict]) -> str:
    """
    生成狙击手标签

    Args:
        code: 股票代码
        hits: get_multi_day_hits()的返回值

    Returns:
        标签字符串，如 "🎯7日内3次" 或 ""
    """
    hit = hits.get(code)
    if not hit:
        return ""
    count = hit["count"]
    dates = hit.get("dates", [])
    dates_str = "/".join(dates[-3:]) if dates else ""
    return f"🎯7日内{count}次({dates_str})"


# ═══════════════════════════════════════════════════════
# 滚动股票池（10日窗口）
# ═══════════════════════════════════════════════════════

def read_gist_file(filename: str) -> Dict:
    """读取 Gist 中指定文件，失败返回 {}。"""
    gid = _gist_id()
    if not gid:
        return {}
    try:
        resp = requests.get(f"{_GIST_API}/{gid}", headers=_headers(), timeout=15)
        resp.raise_for_status()
        content = resp.json().get("files", {}).get(filename, {}).get("content", "{}")
        return json.loads(content) if content else {}
    except Exception as e:
        logger.debug(f"[pool] 读取 {filename} 失败: {e}")
    return {}


def write_gist_files(files: Dict[str, object], description: str = "") -> bool:
    """一次 PATCH 写入多个文件到 Gist。"""
    gid = _gist_id()
    if not gid:
        return False
    try:
        desc = description or f"stock-selector (updated {datetime.now().strftime('%Y-%m-%d %H:%M')})"
        payload = {
            "description": desc,
            "files": {name: {"content": json.dumps(data, ensure_ascii=False, indent=2)}
                      for name, data in files.items()},
        }
        resp = requests.patch(f"{_GIST_API}/{gid}", json=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        logger.debug(f"[pool] 写入 {list(files.keys())} 成功")
        return True
    except Exception as e:
        logger.debug(f"[pool] 写入Gist失败: {e}")
    return False


def save_stock_pool(today_top3: List[Dict]) -> bool:
    """
    保存当日 top3 龙头到滚动池，保留 10 天数据。

    Args:
        today_top3: 当日 top 3 龙头股列表，每项需含 code/name/signal/price/amount_yi/gain_pct

    Returns:
        是否写入成功
    """
    if not today_top3:
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    data = read_gist_file(_POOL_FILENAME)

    # 当日去重（已有当日数据则覆盖）
    today_items = {}
    for r in today_top3:
        code = r.get("code", "")
        if not code:
            continue
        today_items[code] = {
            "code": code,
            "name": r.get("name", ""),
            "signal": r.get("signal", ""),
            "price": r.get("price", 0),
            "amount_yi": r.get("amount_yi", 0),
            "gain_pct": r.get("gain_pct", 0),
            "signal_reason": r.get("signal_reason", ""),
            "sector": r.get("sector", r.get("_sector_name", "")),
        }

    data[today] = list(today_items.values())

    # 清理 10 天前数据
    cutoff = (datetime.now() - timedelta(days=_POOL_RETAIN_DAYS)).strftime("%Y-%m-%d")
    data = {k: v for k, v in data.items() if k >= cutoff}
    logger.info(f"[pool] 保存当日 {len(today_items)} 只，池子共 {sum(len(v) for v in data.values())} 只（{len(data)} 天）")

    return write_gist_files({_POOL_FILENAME: data})


def get_pool_top_n(n: int = 15) -> List[Dict]:
    """
    读取滚动池，按信号优先级 + 成交额排序返回 top N。

    Args:
        n: 返回数量，默认 15

    Returns:
        [{code, name, signal, price, amount_yi, gain_pct, signal_reason, sector, date}, ...]
    """
    data = read_gist_file(_POOL_FILENAME)
    if not data:
        return []

    # 展平所有天，按 code 去重（保留最新一天的数据）
    seen: Dict[str, Dict] = {}
    date_keys = sorted(data.keys(), reverse=True)  # 最新日期优先
    for date_str in date_keys:
        for item in data[date_str]:
            code = item.get("code", "")
            if not code or code in seen:
                continue
            item["date"] = date_str
            seen[code] = item

    pool = list(seen.values())

    # 排序：可介入 > 观望 > 回避 > 其他，同信号按成交额降序
    signal_order = {"可介入": 0, "观望": 1, "回避": 2}
    pool.sort(key=lambda x: (signal_order.get(x.get("signal", ""), 9), -x.get("amount_yi", 0)))

    top = pool[:n]
    logger.info(f"[pool] 池子共 {len(pool)} 只（去重），返回 top {len(top)}")
    return top
