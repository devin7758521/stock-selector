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
_FILENAME = "watchlist.json"
_RETAIN_DAYS = 7


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
