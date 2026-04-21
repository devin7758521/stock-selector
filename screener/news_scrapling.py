# -*- coding: utf-8 -*-
"""
===================================
Scrapling 新闻抓取模块 (A 股适配版)
===================================

借鉴 https://github.com/devin7758521/quant-feishu 的 Scrapling 新闻抓取能力，
适配 A 股场景，支持 basic/stealth 双模式。

特点：
1. 多源中文财经新闻抓取（东方财富、同花顺、新浪、雪球等）
2. 标题去重（前 50 字符小写去重键）
3. 自动降级：Scrapling → requests+BS4 → AkShare 已有逻辑
4. 支持 basic(HTTP) 和 stealth(Playwright) 两种模式

Copyright (c) 2026 stock selector
"""

import logging
import os
import time
from typing import List, Dict, Optional, Set

from .news_akshare import NewsResult, _classify_sentiment, _is_ad

logger = logging.getLogger(__name__)

# A 股适配的 Scrapling 新闻源
# (name, url_template, css_selector, lang)
SCRAPLING_NEWS_SOURCES_A_STOCK = [
    # 个股新闻源
    ("东方财富个股", "https://so.eastmoney.com/web/s?keyword={code}", "h3 a::text, .title a::text", "zh"),
    ("同花顺个股", "http://so.10jqka.com.cn/s?q={code}", ".search-result-title a::text", "zh"),
    ("新浪财经个股", "https://search.sina.com.cn/?q={name}+{code}&range=all&c=news", ".box-result a::text, .result a::text", "zh"),
    ("雪球个股", "https://xueqiu.com/k?q={name}+{code}", ".search__item__title a::text, h3 a::text", "zh"),
    # 宏观/市场新闻源
    ("东方财富财经", "https://so.eastmoney.com/web/s?keyword=宏观经济+A股", "h3 a::text, .title a::text", "zh"),
    ("新浪财经市场", "https://search.sina.com.cn/?q=A股+市场+政策&range=all&c=news", ".box-result a::text", "zh"),
    # 英文财经源（全球视野）
    ("Reuters", "https://www.reuters.com/search/news?query=China+stock+{name}", "h3.search-result-title::text", "en"),
    ("Yahoo Finance", "https://finance.yahoo.com/quote/{code}.SS/news/", "h3 a::text, h3::text", "en"),
    ("Google News", "https://news.google.com/search?q={name}+stock+China&hl=zh-CN", "h3::text, h4::text", "zh"),
    ("Investing.com", "https://www.investing.com/news/stock-market-news", "article a[title]::attr(title)", "en"),
]


def _get_scrapling_mode() -> str:
    """获取 Scrapling 模式：basic 或 stealth"""
    return os.environ.get("SCRAPLING_MODE", "basic").lower()


def _dedup_key(title: str) -> str:
    """生成去重键：标题前 50 字符小写"""
    return (title or "")[:50].lower().strip()


def scrapling_stock_news(
    stock_code: str,
    stock_name: str = "",
    max_per_source: int = 3,
    max_total: int = 10,
    seen_titles: Optional[Set[str]] = None,
) -> List[NewsResult]:
    """
    使用 Scrapling 抓取个股新闻

    Args:
        stock_code: 股票代码（6位）
        stock_name: 股票名称
        max_per_source: 每个源最多抓取条数
        max_total: 总共最多返回条数
        seen_titles: 已见标题集合（跨调用去重）

    Returns:
        新闻列表
    """
    if seen_titles is None:
        seen_titles = set()

    code_6 = stock_code.zfill(6)[-6:] if stock_code else ""
    all_news: List[NewsResult] = []
    mode = _get_scrapling_mode()

    try:
        if mode == "stealth":
            from scrapling.fetchers import StealthyFetcher
            fetch = StealthyFetcher.fetch
            logger.info("Scrapling mode: stealth (Playwright-based)")
        else:
            from scrapling.fetchers import Fetcher
            fetch = Fetcher.fetch
            logger.info("Scrapling mode: basic (HTTP)")

        for src_name, url_tpl, css_sel, lang in SCRAPLING_NEWS_SOURCES_A_STOCK:
            if len(all_news) >= max_total:
                break

            try:
                url = url_tpl.format(code=code_6, name=stock_name or code_6)
                if mode == "stealth":
                    page = fetch(url, headless=True, network_idle=True, timeout=15)
                else:
                    page = fetch(url, timeout=15)

                titles = page.css(css_sel)
                for el in titles[:max_per_source]:
                    text = el.get() if hasattr(el, 'get') else (el.text.strip() if hasattr(el, 'text') else str(el).strip())
                    if not text or len(text) < 10 or _is_ad(text):
                        continue
                    key = _dedup_key(text)
                    if key in seen_titles:
                        continue
                    seen_titles.add(key)

                    news = NewsResult(
                        title=text,
                        content="",
                        url="",
                        source=src_name,
                        pub_date=""
                    )
                    all_news.append(news)

                time.sleep(0.3)

            except Exception as e:
                logger.debug(f"Scrapling {src_name} for {code_6}: {e}")
                continue

        if all_news:
            logger.info(f"Scrapling 个股新闻({code_6}): 获取到 {len(all_news)} 条")

    except ImportError:
        logger.info("scrapling 未安装，跳过 Scrapling 新闻抓取 (pip install scrapling)")
    except Exception as e:
        logger.warning(f"Scrapling 新闻抓取失败: {e}")

    return all_news[:max_total]


def scrapling_market_news(
    max_per_source: int = 3,
    max_total: int = 15,
    seen_titles: Optional[Set[str]] = None,
) -> List[NewsResult]:
    """
    使用 Scrapling 抓取市场/宏观新闻

    Args:
        max_per_source: 每个源最多抓取条数
        max_total: 总共最多返回条数
        seen_titles: 已见标题集合

    Returns:
        新闻列表
    """
    if seen_titles is None:
        seen_titles = set()

    all_news: List[NewsResult] = []
    mode = _get_scrapling_mode()

    # 只使用宏观/市场相关的源
    macro_sources = [
        s for s in SCRAPLING_NEWS_SOURCES_A_STOCK
        if any(kw in s[0] for kw in ["财经", "市场", "Reuters", "Investing", "Google"])
    ]

    try:
        if mode == "stealth":
            from scrapling.fetchers import StealthyFetcher
            fetch = StealthyFetcher.fetch
        else:
            from scrapling.fetchers import Fetcher
            fetch = Fetcher.fetch

        for src_name, url_tpl, css_sel, lang in macro_sources:
            if len(all_news) >= max_total:
                break

            try:
                # 宏观源直接用模板URL（已包含搜索词）
                url = url_tpl.format(code="", name="")
                if mode == "stealth":
                    page = fetch(url, headless=True, network_idle=True, timeout=15)
                else:
                    page = fetch(url, timeout=15)

                titles = page.css(css_sel)
                for el in titles[:max_per_source]:
                    text = el.get() if hasattr(el, 'get') else (el.text.strip() if hasattr(el, 'text') else str(el).strip())
                    if not text or len(text) < 10 or _is_ad(text):
                        continue
                    key = _dedup_key(text)
                    if key in seen_titles:
                        continue
                    seen_titles.add(key)

                    news = NewsResult(
                        title=text,
                        content="",
                        url="",
                        source=src_name,
                        pub_date=""
                    )
                    all_news.append(news)

                time.sleep(0.3)

            except Exception as e:
                logger.debug(f"Scrapling 宏观 {src_name}: {e}")
                continue

        if all_news:
            logger.info(f"Scrapling 市场新闻: 获取到 {len(all_news)} 条")

    except ImportError:
        logger.info("scrapling 未安装，跳过 Scrapling 市场新闻")
    except Exception as e:
        logger.warning(f"Scrapling 市场新闻抓取失败: {e}")

    return all_news[:max_total]


def scrapling_stock_news_fallback(
    stock_code: str,
    stock_name: str = "",
    max_results: int = 5,
) -> List[NewsResult]:
    """
    Scrapling 不可用时的轻量备用方案：requests + BS4 抓取多源

    Args:
        stock_code: 股票代码
        stock_name: 股票名称
        max_results: 最大返回条数

    Returns:
        新闻列表
    """
    import requests
    from bs4 import BeautifulSoup

    results: List[NewsResult] = []
    code_6 = stock_code.zfill(6)[-6:] if stock_code else ""
    seen: Set[str] = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    }

    # 多源并发尝试
    sources = [
        {
            "name": "东方财富",
            "url": f"http://so.eastmoney.com/web/s?keyword={code_6}",
            "selectors": ["h3 a", "li a", ".title a"],
        },
        {
            "name": "新浪财经",
            "url": f"https://search.sina.com.cn/?q={stock_name or code_6}+股票&range=all&c=news",
            "selectors": [".box-result a", ".result a", "a"],
        },
        {
            "name": "同花顺",
            "url": f"http://so.10jqka.com.cn/s?q={stock_name or code_6}",
            "selectors": [".search-result-title a", ".result-item a", "a"],
        },
    ]

    for src in sources:
        if len(results) >= max_results:
            break
        try:
            resp = requests.get(src["url"], headers=headers, timeout=8)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for sel in src["selectors"]:
                if len(results) >= max_results:
                    break
                items = soup.select(sel)
                for item in items:
                    if len(results) >= max_results:
                        break
                    title = item.get_text(strip=True)
                    if not title or len(title) < 10 or _is_ad(title):
                        continue
                    key = _dedup_key(title)
                    if key in seen:
                        continue
                    seen.add(key)

                    link = item.get("href", "")
                    results.append(NewsResult(
                        title=title,
                        content="",
                        url=link if link.startswith("http") else "",
                        source=src["name"],
                        pub_date=""
                    ))
        except Exception as e:
            logger.debug(f"备用搜索 {src['name']}({code_6}) 失败: {e}")

    if results:
        logger.info(f"多源备用搜索({code_6}): 获取 {len(results)} 条")
    return results
